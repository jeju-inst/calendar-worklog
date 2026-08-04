#!/usr/bin/env python3
"""오늘의 할 일 Slack 리스트 동기화 — 브리핑이 뽑은 오늘 할 일을 리스트에 반영한다.

왜 이렇게 하나
--------------
Slack Lists(todo_mode)는 항목의 완료 상태를 **Slack 서버에 네이티브 저장**하므로,
우리 쪽 상시 서버(Interactivity Request URL/Socket Mode)가 필요 없다. 봇 토큰(xoxb)+
`lists:write` 로 스크립트가 1회 호출로 항목을 갈아끼우면 된다. 완료 항목은 todo_mode 가
자동으로 접어 숨긴다.

동기화 규칙 (기본: 이월. 완료정리는 꺼짐)
  1) 현재 리스트 항목을 **전 페이지** 읽는다(커서 끝까지).
  2) `purge_completed` 가 켜져 있으면 완료된 항목을 삭제한다. **기본은 꺼짐.**
  3) 남은 항목 이름을 집합으로 둔다 → **이월**(어제 못 끝낸 것·사용자가 손수 넣은 것 보존).
  4) 입력(오늘 할 일)에서 **이미 있는 이름이 아닌 것만 추가**한다(중복 방지).
     - 마감일이 지정돼 있으면 todo_due_date 컬럼에 함께 세팅.
  5) 대상 사용자에게 접근권을 보장(idempotent).

입력이 비어 있어도(할 일 없는 날) 1·2·5 유지보수는 그대로 돈다 — 추가만 건너뛴다.

입력 형식 (stdin, 한 줄 = 한 항목; 빈 줄 무시):
    웍스 폴더 정리 → 원장실 보고 | due:2026-08-04
    0727 홍보 강영준 논의 | due:2026-08-05
    JAIX 플로우차트 정리
  `| due:YYYY-MM-DD` 는 선택.  `#` 로 시작하는 줄은 주석.

설정: ~/.config/calendar-worklog/todo-list.json (env TODO_LIST_CONFIG 로 경로 override).
토큰: notify.py 와 동일(env SLACK_BOT_TOKEN 또는 ~/.config/.../slack-bot-token).

종료코드
  0  성공. **설정 파일이 없어 기능을 안 쓰는 환경도 0** — 미설정은 실패가 아니다.
     (여기서 1을 내면 이 기능을 안 쓰는 맥에서 성공한 브리핑마다 실패 로그가 찍힌다.)
  1  실패: 토큰 없음, 설정 깨짐, API 오류, **항목 추가·마감일 세팅 일부 실패**.
     일부만 실패해도 0을 내면 러너가 "동기화 완료"로 보고해 빠진 할 일이 묻힌다.
"""
import json
import os
import sys
import urllib.request
import urllib.error

CFG_DIR = os.path.expanduser("~/.config/calendar-worklog")
MAX_PAGES = 50          # 커서 루프 안전장치(=5000건). 서버가 커서를 안 비워도 안 돈다.


def die(msg):
    sys.stderr.write("list-sync: " + msg + "\n")
    sys.exit(1)


def warn(msg):
    sys.stderr.write("list-sync: " + msg + "\n")


def read_token():
    t = os.environ.get("SLACK_BOT_TOKEN")
    if t:
        return t.strip()
    p = os.path.join(CFG_DIR, "slack-bot-token")
    if os.path.exists(p):
        return open(p).read().strip()
    return None


def config_path():
    return os.environ.get("TODO_LIST_CONFIG") or os.path.join(CFG_DIR, "todo-list.json")


def read_config():
    """설정을 읽는다. 파일이 아예 없으면 None(=미설정, 실패 아님). 깨졌으면 die."""
    p = config_path()
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception as e:
        die(f"리스트 설정을 읽을 수 없음 ({p}) — {e}")


def api(token, method, payload):
    """Slack API 호출. 어떤 실패든 {'ok': False, 'error': ...} 로 돌려준다.

    네트워크 단절(URLError)이나 비-JSON 에러 바디(429/5xx 의 HTML 등)에서 트레이스백으로
    죽지 않게 한다 — 이 스크립트는 브리핑 성공 뒤 후처리라, 죽는 방식이 아니라 세는 방식
    으로 실패를 알려야 한다. (notify.py 와 같은 방침.)
    """
    req = urllib.request.Request(
        "https://slack.com/api/" + method,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        body, status = e.read(), e.code
    except Exception as e:                      # URLError·타임아웃·소켓 오류
        return {"ok": False, "error": f"network: {e}"}
    try:
        return json.loads(body)
    except ValueError:
        return {"ok": False, "error": f"http {status}: JSON 아닌 응답"}


def fetch_items(token, list_id):
    """리스트 항목을 **커서 끝까지** 읽는다. (items, error).

    한 페이지(100건)만 읽으면 리스트가 커진 뒤 조용히 무너진다 — 뒷 페이지의 완료 항목은
    영영 안 지워지고, 뒷 페이지에 이미 있는 할 일은 '없다'고 판단해 매일 중복 추가된다.
    """
    out, cursor = [], None
    for _ in range(MAX_PAGES):
        payload = {"list_id": list_id, "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        r = api(token, "slackLists.items.list", payload)
        if not r.get("ok"):
            return None, r.get("error")
        out.extend(r.get("items", []))
        cursor = (r.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            return out, None
    return out, f"페이지가 {MAX_PAGES}장을 넘음 — 목록을 다 읽지 못했다"


def item_fields(it):
    """(name, done) 추출."""
    name, done = "", False
    for f in it.get("fields", []):
        if f.get("key") == "name":
            name = f.get("text", "")
        if f.get("key") == "todo_completed":
            done = bool(f.get("value"))
    return name, done


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
    cfg = read_config()
    if cfg is None:
        # 미설정은 실패가 아니다. 이 기능을 안 쓰는 환경에서도 조용히 0 으로 끝난다.
        print(f"list-sync: 리스트 설정 없음 — 동기화 건너뜀 ({config_path()})")
        return 0
    token = read_token()
    if not token:
        die("Slack 토큰 없음")
    LIST = cfg["list_id"]
    NAME = cfg["name_column_id"]
    DUE = cfg.get("due_column_id")
    purge = cfg.get("purge_completed", False)   # 기본 꺼짐 — 아래 2) 주석 참조
    share_user = cfg.get("share_user_id")

    # 입력이 비어도 멈추지 않는다 — 할 일이 없는 날에도 완료정리·공유보장은 돌아야 한다.
    items = parse_input(sys.stdin.read())
    failed = 0

    # 1) 현재 항목 읽기 (전 페이지)
    raw_items, err = fetch_items(token, LIST)
    if raw_items is None:
        die(f"items.list 실패 — {err}")
    if err:
        warn(err)
        failed += 1
    cur = []
    for it in raw_items:
        name, done = item_fields(it)
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
                warn(f"완료항목 삭제 실패 — {rr.get('error')}")
                failed += 1

    # 3) 남아있는 항목 이름 집합 — 이월·중복방지 기준.
    # 완료 항목도 (삭제하지 않았다면) 포함한다 → 완료한 걸 다음날 다시 안 만든다.
    existing = {c["name"].strip() for c in cur if c["id"] not in purged_ids}
    carried = len(existing)

    # 4) 새 항목만 추가
    added = 0
    name_to_id = None                   # create 응답에 id 가 없을 때 쓸 조회 캐시
    for text, due in items:
        if text.strip() in existing:
            continue
        rr = api(token, "slackLists.items.create",
                 {"list_id": LIST,
                  "initial_fields": [{"column_id": NAME, "rich_text": rich_text(text)}]})
        if not rr.get("ok"):
            # 여기서 세어두지 않으면 할 일이 빠진 채로 러너에 "동기화 완료"가 찍힌다.
            warn(f"추가 실패 '{text[:20]}' — {rr.get('error')}")
            failed += 1
            continue
        added += 1
        existing.add(text.strip())
        if not (due and DUE):
            continue
        # 마감일. 실패를 삼키면 안 된다 — 이름은 이미 리스트에 있으므로 다음 실행은 이
        # 항목을 건너뛰고, 마감일은 영영 안 붙는다(재시도 기회가 없다).
        rid = (rr.get("item") or {}).get("id") or rr.get("id")
        if not rid:
            if name_to_id is None:      # 항목마다 재조회하지 않도록 1회만 캐시
                relisted, rerr = fetch_items(token, LIST)
                name_to_id = {}
                if relisted is None:
                    warn(f"마감일용 재조회 실패 — {rerr}")
                else:
                    for it in relisted:
                        nm, _ = item_fields(it)
                        name_to_id.setdefault(nm.strip(), it["id"])
            rid = name_to_id.get(text.strip())
        if not rid:
            warn(f"마감일 세팅 실패 '{text[:20]}' — 항목 id 를 찾지 못함")
            failed += 1
            continue
        ur = api(token, "slackLists.items.update",
                 {"list_id": LIST,
                  "cells": [{"row_id": rid, "column_id": DUE, "date": [due]}]})
        if not ur.get("ok"):
            warn(f"마감일 세팅 실패 '{text[:20]}' — {ur.get('error')}")
            failed += 1

    # 5) 공유 보장
    if share_user:
        ar = api(token, "slackLists.access.set",
                 {"list_id": LIST, "access_level": "write", "user_ids": [share_user]})
        if not ar.get("ok"):
            warn(f"공유 설정 실패 — {ar.get('error')}")
            failed += 1

    print(f"list-sync: 완료정리 {purged}건 · 신규 {added}건 · 이월 {carried}건"
          + (f" · 실패 {failed}건" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
