#!/usr/bin/env python3
"""오늘의 할 일 Slack **캔버스** 동기화 — 브리핑이 뽑은 오늘 할 일을 캔버스 체크리스트로.

왜 캔버스인가 (리스트+스냅샷 이원화 해소, 2026-08-12)
----------------------------------------------------
기존엔 (a) Slack List(todo_mode, 체크가능) + (b) 텍스트 스냅샷 DM(맥락·설명)으로 둘이 따로
놀았다. 캔버스는 **한 문서에 "할 일 + 설명 + 체크박스"**를 담고, 사용자가 체크하면 취소선/완료가
Slack 서버에 네이티브로 저장된다(우리 상시 서버 불필요 — 리스트와 동일 원리). 게다가 캔버스는
삭제 API가 있어(리스트와 달리) 오래된 것을 자동 정리할 수 있다.

한계 (수용): 캔버스는 **체크 상태를 API로 되읽을 방법이 없다**(canvases.read 부재,
sections.lookup 은 체크 상태 미반환). 그래서 "완료 몇 건" 자동 집계는 불가. 이 키트는
가벼운 1회용 일일 리뷰라 이를 수용한다. (전사 집계가 필요해지면 그때 별도 방식 재검토.)

동작 (매일 아침)
  1) 오늘 할 일을 캔버스 체크리스트로 **새로 생성**(canvases.create). 항목 = `- [ ] 할일 · _설명(~기한)_`.
  2) 대상 사용자에게 write 공유(canvases.access.set) + 링크 DM(chat.postMessage).
  3) 생성 이력을 기록하고, **N일 지난 캔버스는 삭제**(canvases.delete)로 누적 방지.
     → 각 날짜 캔버스가 그날의 "체크된 기록"으로 남고, 오래된 건 자동 정리.

입력 형식 (stdin): `<할 일> | due:YYYY-MM-DD | note:<맥락>`  (due·note 선택, 순서 무관).
설정: ~/.config/calendar-worklog/todo-list.json (env TODO_LIST_CONFIG). 캔버스 관련 키:
  share_user_id, history_target(DM 대상, 없으면 share_user_id), canvas_url_base,
  canvas_title_prefix(기본 "오늘의 할 일"), canvas_keep_days(기본 14).
토큰: SLACK_BOT_TOKEN 또는 ~/.config/.../slack-bot-token. 스코프 canvases:write 필요(+재설치).

종료코드: 0 성공/미설정(실패 아님) · 1 실패(토큰·설정·API 오류). 입력이 비면 캔버스를 만들지
않고 프루닝만 수행(빈 입력으로 빈 캔버스를 만드는 사고 방지).
"""
import datetime
import json
import os
import sys
import urllib.request
import urllib.error

CFG_DIR = os.path.expanduser("~/.config/calendar-worklog")
CANVAS_LOG = os.path.join(CFG_DIR, "todo-canvas-log.json")


def die(msg):
    sys.stderr.write("canvas-sync: " + msg + "\n")
    sys.exit(1)


def warn(msg):
    sys.stderr.write("canvas-sync: " + msg + "\n")


def read_token():
    t = os.environ.get("SLACK_BOT_TOKEN")
    if t:
        return t.strip()
    p = os.path.join(CFG_DIR, "slack-bot-token")
    return open(p).read().strip() if os.path.exists(p) else None


def config_path():
    return os.environ.get("TODO_LIST_CONFIG") or os.path.join(CFG_DIR, "todo-list.json")


def read_config():
    p = config_path()
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception as e:
        die(f"설정을 읽을 수 없음 ({p}) — {e}")


def api(token, method, payload):
    req = urllib.request.Request(
        "https://slack.com/api/" + method,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        body, status = e.read(), e.code
    except Exception as e:
        return {"ok": False, "error": f"network: {e}"}
    try:
        return json.loads(body)
    except ValueError:
        return {"ok": False, "error": f"http {status}: JSON 아닌 응답"}


def parse_input(raw):
    """`<할 일> | due:YYYY-MM-DD | note:<맥락>` → [(text, due, note)]."""
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        text, due, note = parts[0].strip(), None, None
        for seg in parts[1:]:
            if seg.startswith("due:"):
                due = seg[4:].strip() or None
            elif seg.startswith("note:"):
                note = seg[5:].strip() or None
        if text:
            out.append((text, due, note))
    return out


def compact_due(due):
    try:
        p = due.split("-")
        return f"~{int(p[1])}/{int(p[2])}"
    except Exception:
        return ""


def build_markdown(day, items):
    """캔버스 체크리스트 markdown. 각 항목 한 줄: `- [ ] 할일 · _설명 · ~M/D_`."""
    wd = "월화수목금토일"[day.weekday()]
    lines = [f"# 📋 오늘의 할 일 — {day.month}/{day.day} ({wd})", ""]
    for text, due, note in items:
        bits = []
        if note:
            bits.append(note)
        if due and compact_due(due):
            bits.append(compact_due(due))
        # 설명은 체크박스와 같은 줄에 접는다. 들여쓴 줄로 넣으면 체크리스트 파싱이 꼬임(실측).
        tail = f"  ·  _{' · '.join(bits)}_" if bits else ""
        lines.append(f"- [ ] {text}{tail}")
    return "\n".join(lines)


def read_log():
    try:
        return json.load(open(CANVAS_LOG))
    except Exception:
        return []


def write_log(log):
    try:
        json.dump(log, open(CANVAS_LOG, "w"), ensure_ascii=False)
    except Exception as e:
        warn(f"캔버스 로그 저장 실패 — {e}")


def prune_old(token, log, keep_days, today):
    """keep_days 지난 캔버스를 삭제. (살아남은 log, 삭제수, 실패수)."""
    cutoff = today - datetime.timedelta(days=keep_days)
    kept, deleted, failed = [], 0, 0
    for e in log:
        try:
            d = datetime.date.fromisoformat(e.get("date", ""))
        except Exception:
            kept.append(e)
            continue
        if d < cutoff:
            r = api(token, "canvases.delete", {"canvas_id": e["canvas_id"]})
            if r.get("ok") or r.get("error") == "canvas_not_found":
                deleted += 1
            else:
                warn(f"오래된 캔버스 삭제 실패 {e['canvas_id']} — {r.get('error')}")
                kept.append(e)
                failed += 1
        else:
            kept.append(e)
    return kept, deleted, failed


def main():
    cfg = read_config()
    if cfg is None:
        print(f"canvas-sync: 설정 없음 — 건너뜀 ({config_path()})")
        return 0
    token = read_token()
    if not token:
        die("Slack 토큰 없음")
    share_user = cfg.get("share_user_id")
    dm_target = cfg.get("history_target") or share_user
    url_base = (cfg.get("canvas_url_base") or "").rstrip("/")
    prefix = cfg.get("canvas_title_prefix", "오늘의 할 일")
    keep_days = int(cfg.get("canvas_keep_days", 14))

    items = parse_input(sys.stdin.read())
    today = datetime.date.today()
    failed = 0

    # 1) 오늘 캔버스 생성 (입력이 있을 때만 — 빈 입력으로 빈 캔버스 만들지 않는다)
    created_id = None
    if items:
        wd = "월화수목금토일"[today.weekday()]
        title = f"{prefix} · {today.month}/{today.day}({wd})"
        md = build_markdown(today, items)
        r = api(token, "canvases.create",
                {"title": title, "document_content": {"type": "markdown", "markdown": md}})
        if not r.get("ok"):
            die(f"canvases.create 실패 — {r.get('error')}")
        created_id = r.get("canvas_id")

        # 2) 공유 + DM
        if share_user and created_id:
            ar = api(token, "canvases.access.set",
                     {"canvas_id": created_id, "access_level": "write", "user_ids": [share_user]})
            if not ar.get("ok"):
                warn(f"공유 설정 실패 — {ar.get('error')}")
                failed += 1
        if dm_target and created_id and url_base:
            url = f"{url_base}/{created_id}"
            dm = api(token, "chat.postMessage",
                     {"channel": dm_target, "username": "일정관리봇",
                      "icon_emoji": ":spiral_calendar_pad:",
                      "text": f"*📋 오늘의 할 일 ({today.month}/{today.day})* — 체크하며 진행하세요.\n{url}"})
            if not dm.get("ok"):
                warn(f"링크 DM 실패 — {dm.get('error')}")
                failed += 1

    # 3) 이력 갱신 + 오래된 캔버스 프루닝
    log = read_log()
    if created_id:
        log.append({"canvas_id": created_id, "date": today.isoformat()})
    log, deleted, pfail = prune_old(token, log, keep_days, today)
    failed += pfail
    write_log(log)

    made = "생성 1" if created_id else "생성 0(입력 없음)"
    print(f"canvas-sync: {made} · 프루닝 {deleted}건 · 보관 {len(log)}건"
          + (f" · 실패 {failed}건" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
