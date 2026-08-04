#!/usr/bin/env python3
"""오늘의 할 일 Slack 리스트 동기화 — 브리핑이 뽑은 오늘 할 일을 리스트에 반영한다.

왜 이렇게 하나
--------------
Slack Lists(todo_mode)는 항목의 완료 상태를 **Slack 서버에 네이티브 저장**하므로,
우리 쪽 상시 서버(Interactivity Request URL/Socket Mode)가 필요 없다. 봇 토큰(xoxb)+
`lists:write` 로 스크립트가 1회 호출로 항목을 갈아끼우면 된다. 완료 항목은 todo_mode 가
자동으로 접어 숨긴다.

동기화 규칙 (기본: 이월 + 완료정리)
  1) 현재 리스트 항목을 읽는다.
  2) `purge_completed` 면 **완료된 항목을 삭제**한다(끝난 건 치운다).
  3) 남은 미완료 항목 이름을 집합으로 둔다 → **이월**(어제 못 끝낸 것·사용자가 손수 넣은 것 보존).
  4) 입력(오늘 할 일)에서 **이미 있는 이름이 아닌 것만 추가**한다(중복 방지).
     - 마감일이 지정돼 있으면 todo_due_date 컬럼에 함께 세팅.
  5) 대상 사용자에게 접근권을 보장(idempotent).

입력 형식 (stdin, 한 줄 = 한 항목; 빈 줄 무시):
    웍스 폴더 정리 → 원장실 보고 | due:2026-08-04
    0727 홍보 강영준 논의 | due:2026-08-05
    JAIX 플로우차트 정리
  `| due:YYYY-MM-DD` 는 선택.  `#` 로 시작하는 줄은 주석.

설정: ~/.config/calendar-worklog/todo-list.json (env TODO_LIST_CONFIG 로 경로 override).
토큰: notify.py 와 동일(env SLACK_BOT_TOKEN 또는 ~/.config/.../slack-bot-token).

종료코드: 0 성공 / 1 실패(설정·토큰 없음, API 오류). 브리핑 러너가 실패를 로그로 남길 수 있게.
"""
import json
import os
import sys
import urllib.request
import urllib.error

CFG_DIR = os.path.expanduser("~/.config/calendar-worklog")


def die(msg):
    sys.stderr.write("list-sync: " + msg + "\n")
    sys.exit(1)


def read_token():
    t = os.environ.get("SLACK_BOT_TOKEN")
    if t:
        return t.strip()
    p = os.path.join(CFG_DIR, "slack-bot-token")
    if os.path.exists(p):
        return open(p).read().strip()
    return None


def read_config():
    p = os.environ.get("TODO_LIST_CONFIG") or os.path.join(CFG_DIR, "todo-list.json")
    if not os.path.exists(p):
        die(f"리스트 설정 없음: {p}")
    return json.load(open(p))


def api(token, method, payload):
    req = urllib.request.Request(
        "https://slack.com/api/" + method,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e:
        return json.load(e)


def rich_text(text):
    return [{"type": "rich_text",
             "elements": [{"type": "rich_text_section",
                           "elements": [{"type": "text", "text": text}]}]}]


def parse_input(raw):
    """줄 단위 파싱 → [(text, due_or_None)]."""
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        due = None
        if "| due:" in line:
            line, _, d = line.partition("| due:")
            line = line.strip()
            due = d.strip() or None
        if line:
            out.append((line, due))
    return out


def main():
    token = read_token()
    if not token:
        die("Slack 토큰 없음")
    cfg = read_config()
    LIST = cfg["list_id"]
    NAME = cfg["name_column_id"]
    DUE = cfg.get("due_column_id")
    COMPLETED = cfg.get("completed_column_id", "Col00")
    purge = cfg.get("purge_completed", True)
    share_user = cfg.get("share_user_id")

    items = parse_input(sys.stdin.read())
    if not items:
        print("list-sync: 입력 항목 없음 — 리스트 변경 안 함")
        return

    # 1) 현재 항목 읽기
    r = api(token, "slackLists.items.list", {"list_id": LIST, "limit": 100})
    if not r.get("ok"):
        die(f"items.list 실패 — {r.get('error')}")
    cur = []
    for it in r.get("items", []):
        name, done = "", False
        for f in it["fields"]:
            if f["key"] == "name":
                name = f.get("text", "")
            if f["key"] == "todo_completed":
                done = bool(f.get("value"))
        cur.append({"id": it["id"], "name": name, "done": done})

    # 2) (선택) 완료 항목 정리 — 기본 꺼짐.
    # todo_mode 는 완료 항목을 네이티브로 접어 숨기므로 삭제할 필요가 없다. 오히려 켜두면
    # 사용자가 "확인차" 체크한 것까지 다음 실행에 사라져 놀란다. 정말 데이터를 비우고
    # 싶을 때만 config 의 purge_completed 를 true 로.
    purged = 0
    purged_ids = set()
    if purge:
        done_ids = [c["id"] for c in cur if c["done"]]
        if done_ids:
            rr = api(token, "slackLists.items.deleteMultiple",
                     {"list_id": LIST, "ids": done_ids})
            if rr.get("ok"):
                purged = len(done_ids)
                purged_ids = set(done_ids)
            else:
                sys.stderr.write(f"list-sync: 완료항목 삭제 실패 — {rr.get('error')}\n")

    # 3) 남아있는 항목 이름 집합 — 이월·중복방지 기준.
    # 완료 항목도 (삭제하지 않았다면) 포함한다 → 완료한 걸 다음날 다시 안 만든다.
    existing = {c["name"].strip() for c in cur if c["id"] not in purged_ids}

    # 4) 새 항목만 추가
    added = 0
    for text, due in items:
        if text.strip() in existing:
            continue
        rr = api(token, "slackLists.items.create",
                 {"list_id": LIST,
                  "initial_fields": [{"column_id": NAME, "rich_text": rich_text(text)}]})
        if not rr.get("ok"):
            sys.stderr.write(f"list-sync: 추가 실패 '{text[:20]}' — {rr.get('error')}\n")
            continue
        added += 1
        existing.add(text.strip())
        # 마감일
        if due and DUE:
            rid = rr.get("item", {}).get("id") or rr.get("id")
            if not rid:
                # create 응답에 id 가 없으면 재조회로 찾는다
                lr = api(token, "slackLists.items.list", {"list_id": LIST, "limit": 100})
                for it in lr.get("items", []):
                    nm = next((f.get("text", "") for f in it["fields"] if f["key"] == "name"), "")
                    if nm.strip() == text.strip():
                        rid = it["id"]
                        break
            if rid:
                api(token, "slackLists.items.update",
                    {"list_id": LIST,
                     "cells": [{"row_id": rid, "column_id": DUE, "date": [due]}]})

    # 5) 공유 보장
    if share_user:
        api(token, "slackLists.access.set",
            {"list_id": LIST, "access_level": "write", "user_ids": [share_user]})

    print(f"list-sync: 완료정리 {purged}건 · 신규 {added}건 · 이월 {len(existing)-added}건")


if __name__ == "__main__":
    main()
