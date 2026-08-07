#!/usr/bin/env python3
"""오늘의 할 일 Slack 리스트 동기화 — 브리핑이 뽑은 오늘 할 일을 리스트에 반영한다.

왜 이렇게 하나
--------------
Slack Lists(todo_mode)는 항목의 완료 상태를 **Slack 서버에 네이티브 저장**하므로,
우리 쪽 상시 서버(Interactivity Request URL/Socket Mode)가 필요 없다. 봇 토큰(xoxb)+
`lists:write` 로 스크립트가 1회 호출로 항목을 갈아끼우면 된다. 완료 항목은 todo_mode 가
자동으로 접어 숨긴다.

동기화 모드 (config 의 sync_mode, 기본 "replace")
  - **"replace" (기본, 1회용 일일 리뷰)**: 매일 아침 기존 항목을 **전부 지우고** 오늘 것만
    새로 채운다. 누적 0, 링크 고정, 그날 할 일만. 지속·헤비 관리는 monday 가 하므로
    이월하지 않는다(완료 히스토리도 안 남긴다 — 가볍게 쓰고 버린다). 단, **입력이 비면
    지우지 않는다** — 빈 입력으로 리스트를 실수로 비우는 사고를 막는다.
  - "carryover": 기존 항목을 남기고(이월) **없는 이름만 추가**(중복 방지). `purge_completed`
    가 켜져 있으면 완료 항목만 정리. 이 리스트를 지속 트래커로 쓰고 싶을 때.

공통 절차
  1) 현재 리스트 항목을 **전 페이지** 읽는다(커서 끝까지) — 완료 체크 상태 포함.
  1.5) (replace) **전날 계획 메시지 완료반영**: 저장해 둔 어제 계획 DM 을 chat.update 로
       고쳐, 그 사이 리스트에서 완료 체크된 항목을 ~취소선~ 으로 긋는다(지우기 직전 박제).
  2) (carryover+purge) 완료 항목만 미리 정리. **replace 는 여기서 안 지운다.**
  3) 오늘 할 일을 추가한다(+마감일). replace 는 전부 새로, carryover 는 없는 이름만.
  4) (replace) 추가가 **다 성공하면 그제서야** 옛 항목을 지운다 — 지우고 나서 만들다 실패해
     리스트가 통째로 비는 사고를 막는다. 입력이 비거나 생성 실패가 있으면 안 지운다.
  5) 대상 사용자에게 접근권을 보장(idempotent).
  5.5) 리스트 제목을 오늘 날짜로 갱신(`list_title_prefix · M/D(요일)`).
  6) `post_history`(기본 켜짐)면 **오늘 계획 스냅샷**(그날 할 일 + note 설명 + 리스트 링크)을
     일정관리봇 DM 으로 게시하고 그 ts 를 저장한다(다음날 1.5 에서 완료반영에 씀). 리스트가
     비어도 이 DM 이 append-only 히스토리로 남는다. 중장기 전사 업무현황 집계 소스로 쓸 형태.

입력 형식 (stdin, 한 줄 = 한 항목; 빈 줄 무시):
    서귀포축제 보고서 확인·수정 → 디자인오투 발송 | due:2026-08-04 | note:이중화 박사가 E-2·E-3 2건 확인 요청, 확인 후 메일 발송 (그가 대기 중)
    JAIX 플로우차트 정리 | due:2026-08-07
  `| due:YYYY-MM-DD`, `| note:<맥락 한 줄>` 은 선택(순서 무관). `#` 로 시작하는 줄은 주석.
  text 는 **리스트 항목(짧게)**, note 는 **히스토리 스냅샷의 설명**(리스트엔 안 들어감).

설정: ~/.config/calendar-worklog/todo-list.json (env TODO_LIST_CONFIG 로 경로 override).
토큰: notify.py 와 동일(env SLACK_BOT_TOKEN 또는 ~/.config/.../slack-bot-token).

종료코드
  0  성공. **설정 파일이 없어 기능을 안 쓰는 환경도 0** — 미설정은 실패가 아니다.
     (여기서 1을 내면 이 기능을 안 쓰는 맥에서 성공한 브리핑마다 실패 로그가 찍힌다.)
  1  실패: 토큰 없음, 설정 깨짐, API 오류, **항목 추가·마감일 세팅 일부 실패**.
     일부만 실패해도 0을 내면 러너가 "동기화 완료"로 보고해 빠진 할 일이 묻힌다.
"""
import datetime
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
    """줄 단위 파싱 → [(text, due_or_None, note_or_None)].

    형식: `<할 일> | due:YYYY-MM-DD | note:<맥락 한 줄>`  (due·note 순서 무관, 둘 다 선택).
    text 는 리스트 항목(짧게), note 는 히스토리 스냅샷에만 붙는 설명(왜/출처/차단 여부 등).
    """
    out = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        text = parts[0].strip()
        due = note = None
        for seg in parts[1:]:
            if seg.startswith("due:"):
                due = seg[4:].strip() or None
            elif seg.startswith("note:"):
                note = seg[5:].strip() or None
        if text:
            out.append((text, due, note))
    return out


SNAPSHOT_STATE = os.path.join(CFG_DIR, "todo-last-snapshot.json")


def compact_due(due):
    """'YYYY-MM-DD' → '  _~M/D_'. 파싱 실패면 빈 문자열."""
    try:
        p = due.split("-")
        return f"  _~{int(p[1])}/{int(p[2])}_"
    except Exception:
        return ""


def render_plan(day, items, done_texts, list_url):
    """계획 스냅샷 메시지 텍스트. done_texts 에 든 항목 text 는 제목에 취소선(~..~ ✅).

    day: datetime.date. items: [(text, due, note)]. 최초 게시 때는 done_texts 가 비어 있고,
    다음날 완료 반영 때는 리스트에서 체크된 항목 text 집합이 들어와 그 줄을 취소선 처리한다.
    """
    wd = "월화수목금토일"[day.weekday()]
    lines = [f"*📋 오늘 할 일 — {day.month}/{day.day} ({wd})*", ""]
    for i, (text, due, note) in enumerate(items, 1):
        d = compact_due(due) if due else ""
        if text.strip() in done_texts:
            lines.append(f"*{i}.* ~{text}~ ✅{d}")
        else:
            lines.append(f"*{i}.* {text}{d}")
        if note:
            lines.append(f"      ↳ {note}")
    if list_url:
        lines += ["", f"📋 리스트에서 체크: {list_url}"]
    return "\n".join(lines)


def read_snapshot_state():
    """직전에 올린 계획 메시지 상태(채널·ts·날짜·항목). 없으면 None."""
    try:
        return json.load(open(SNAPSHOT_STATE))
    except Exception:
        return None


def write_snapshot_state(state):
    try:
        json.dump(state, open(SNAPSHOT_STATE, "w"), ensure_ascii=False)
    except Exception as e:
        warn(f"스냅샷 상태 저장 실패 — {e}")


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
    mode = str(cfg.get("sync_mode", "replace")).lower()   # replace(기본) | carryover
    if mode not in ("replace", "carryover"):
        # 오타(예: "replcae")를 조용히 carryover 로 흘리면, 지우려던 리스트가 안 지워지고
        # 러너엔 "동기화 완료"로 찍힌다. 알 수 없는 값은 명시적으로 실패시킨다.
        die(f"알 수 없는 sync_mode: '{mode}' — replace|carryover 만 허용")
    purge = cfg.get("purge_completed", False)   # carryover 에서만 의미
    share_user = cfg.get("share_user_id")
    post_history = cfg.get("post_history", True)          # 그날 문장 스냅샷을 DM 으로 남길지
    history_target = cfg.get("history_target") or share_user
    list_url = cfg.get("list_url")                        # 스냅샷 끝에 붙일 리스트 링크
    list_title_prefix = cfg.get("list_title_prefix", "오늘의 할 일")  # 매일 제목을 오늘 날짜로

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

    # 1.5) 전날 계획 메시지에 완료 취소선 반영 (in-place chat.update).
    # 어제 아침 올린 계획 메시지의 각 항목 중, 어제 리스트에서 완료 체크된 것을 ~취소선~ 으로
    # 그어 그 메시지를 그대로 수정한다. replace 로 리스트를 비우기 직전에 리스트의 완료 상태를
    # 읽어 반영하는 것 — 서버 없이 "체크된 항목이 취소선으로 표시"되는 유일한 시점이다
    # (실시간 아님, 다음 동기화 때 1회 반영). carryover 는 리스트가 남으니 하지 않는다.
    updated_prev = False
    prev = read_snapshot_state()
    if post_history and mode == "replace" and prev and prev.get("ts") and prev.get("channel"):
        done_texts = {c["name"].strip() for c in cur if c["done"]}
        try:
            prev_day = datetime.date.fromisoformat(prev.get("date"))
        except Exception:
            prev_day = datetime.date.today()
        prev_items = [tuple(x) for x in prev.get("items", [])]
        if prev_items:
            text = render_plan(prev_day, prev_items, done_texts, prev.get("list_url"))
            ur = api(token, "chat.update",
                     {"channel": prev["channel"], "ts": prev["ts"], "text": text})
            if ur.get("ok"):
                updated_prev = True
            else:
                warn(f"전날 계획 메시지 완료반영 실패 — {ur.get('error')}")
                failed += 1

    # 2) 삭제/추가 전략을 모드별로 정한다.
    #   replace  — 오늘 것을 **먼저 만들고**(3), 다 성공하면 **그다음**에 옛 항목을 지운다(4).
    #              지우고 나서 만들다 실패하면 리스트가 통째로 비는 사고(Codex P1)를 막는다.
    #   carryover — 옛 항목을 남기고(이월), purge 면 완료된 것만 **여기서** 미리 정리한다.
    old_ids = [c["id"] for c in cur]
    deleted, deleted_ids = 0, set()

    def delete_ids(ids, label):
        n = 0
        for i in range(0, len(ids), 100):       # deleteMultiple 배치 보호
            chunk = ids[i:i + 100]
            rr = api(token, "slackLists.items.deleteMultiple",
                     {"list_id": LIST, "ids": chunk})
            if rr.get("ok"):
                n += len(chunk)
                deleted_ids.update(chunk)
            else:
                warn(f"{label} 삭제 실패({len(chunk)}건) — {rr.get('error')}")
                nonlocal failed
                failed += 1
        return n

    if mode == "carryover":
        if purge:
            deleted += delete_ids([c["id"] for c in cur if c["done"]], "완료항목")
        existing = {c["name"].strip() for c in cur if c["id"] not in deleted_ids}
    else:  # replace — 아직 아무것도 안 지운다. 오늘 것을 전부 새로 만든 뒤 4)에서 옛것 삭제.
        existing = set()
    carried = len(existing)

    # 3) 항목 추가 (마감일 포함). replace 는 existing 이 비어 오늘 것 전부가 새로 들어간다.
    added, create_failed = 0, 0
    name_to_id = None                   # create 응답에 id 가 없을 때 쓸 조회 캐시
    for text, due, _note in items:      # note 는 리스트가 아니라 히스토리 스냅샷용
        if text.strip() in existing:
            continue
        rr = api(token, "slackLists.items.create",
                 {"list_id": LIST,
                  "initial_fields": [{"column_id": NAME, "rich_text": rich_text(text)}]})
        if not rr.get("ok"):
            # 여기서 세어두지 않으면 할 일이 빠진 채로 러너에 "동기화 완료"가 찍힌다.
            warn(f"추가 실패 '{text[:20]}' — {rr.get('error')}")
            failed += 1
            create_failed += 1
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

    # 4) replace: 오늘 것을 다 만든 **뒤에야** 옛 항목을 지운다.
    #    - 입력이 비면 지우지 않는다(빈 입력으로 리스트를 날리는 사고 방지 — no-task 날엔
    #      옛 리스트를 남기고 제목·공유만 갱신한다).
    #    - 생성이 하나라도 실패했으면 지우지 않는다. 옛것을 남겨(오늘 것과 잠시 섞이더라도)
    #      빈 리스트보다는 낫게 하고, 러너가 실패로 보고해 다음 실행이 정리하게 둔다.
    if mode == "replace" and items and old_ids:
        if create_failed == 0:
            deleted += delete_ids(old_ids, "옛 항목")
        else:
            warn(f"생성 {create_failed}건 실패 → 옛 항목 보존(빈 리스트 방지), 다음 실행에서 정리")

    # 5) 공유 보장
    if share_user:
        ar = api(token, "slackLists.access.set",
                 {"list_id": LIST, "access_level": "write", "user_ids": [share_user]})
        if not ar.get("ok"):
            warn(f"공유 설정 실패 — {ar.get('error')}")
            failed += 1

    # 5.5) 리스트 제목을 오늘 날짜로 갱신 — 리스트는 재사용되므로 갱신 안 하면 제목이 처음
    # 만든 날짜에 멈춰 "어제 것"처럼 보인다(2026-08-05 피드백). `list_title_prefix` 를 빈 값으로
    # 두면 갱신하지 않는다(날짜 없는 고정 제목을 쓰고 싶을 때 — 수동으로 한 번 정해두면 됨).
    if list_title_prefix:
        t = datetime.date.today()
        title = f"{list_title_prefix} · {t.month}/{t.day}({'월화수목금토일'[t.weekday()]})"
        nr = api(token, "slackLists.update", {"id": LIST, "name": title})
        if not nr.get("ok"):
            warn(f"리스트 제목 갱신 실패 — {nr.get('error')}")
            failed += 1

    # 6) 오늘 계획 스냅샷 게시(히스토리). 그날 할 일 + note 설명 + 리스트 링크를 일정관리봇
    # DM 으로 남긴다. **다음 동기화 때 이 메시지를 chat.update 로 수정해 완료 취소선을 반영**
    # 하므로, 채널·ts·항목을 상태파일에 저장해 둔다. replace 는 리스트를 비우니 이 메시지가
    # append-only 기록이 된다. (중장기 전사 업무현황 집계 소스로 쓸 고정 포맷.)
    if post_history and items and history_target:
        today = datetime.date.today()
        text = render_plan(today, items, set(), list_url)   # 최초 게시: 아직 완료 없음
        hr = api(token, "chat.postMessage",
                 {"channel": history_target, "text": text,
                  "username": "일정관리봇", "icon_emoji": ":spiral_calendar_pad:"})
        if hr.get("ok"):
            # channel 은 응답이 준 실제 채널 id(D…) 를 쓴다 — 다음날 chat.update 대상.
            write_snapshot_state({
                "channel": hr.get("channel") or history_target,
                "ts": hr.get("ts"),
                "date": today.isoformat(),
                "items": [list(x) for x in items],
                "list_url": list_url,
            })
        else:
            warn(f"계획 스냅샷 게시 실패 — {hr.get('error')}")
            failed += 1

    marks = []
    if updated_prev:
        marks.append("전날완료반영")
    if post_history and items and history_target:
        marks.append("오늘계획")
    print(f"list-sync: [{mode}] 삭제 {deleted}건 · 신규 {added}건 · 유지 {carried}건"
          + (f" · 스냅샷({'+'.join(marks)})" if marks else "")
          + (f" · 실패 {failed}건" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
