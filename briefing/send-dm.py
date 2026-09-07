#!/usr/bin/env python3
"""브리핑 본문을 Slack Bot Token 으로 본인 DM 에 발송한다 (표준입력=본문).

왜 러너가 보내나 (C-a, 2026-09-07)
--------------------------------
예전엔 모델(claude)이 커넥터(slack_send_message)로 셀프-DM 을 직접 보내고,
러너는 모델이 마지막에 낸 `BRIEFING_SENT` 토큰으로 성공을 판정했다. 그런데 모델이
본문·DM 은 정상 발송해놓고 그 토큰을 빠뜨리면 러너가 성공한 브리핑을 '실패'로 오탐했다
(9/7 실측). 성공 신호가 모델의 마지막 한 줄에 걸려 있던 게 근본 취약점.

이제 **모델은 본문만 stdout 으로 내고, 러너가 이 스크립트로 직접 발송**한다.
`chat.postMessage` 의 `ok`/`ts` 반환값이 성공의 단일 근거다 — 모델 텍스트 파싱이
개입하지 않는다. notify.py(독립 실패 알림)와 같은 봇 경로를 쓴다.

토큰·대상·표시이름은 notify.py 와 동일 규칙:
  토큰   1) $SLACK_BOT_TOKEN  2) ~/.config/calendar-worklog/slack-bot-token
  대상   1) --to  2) $SLACK_NOTIFY_TARGET  3) user-config.yaml 의 user.slack_user_id
  표시   $SLACK_NOTIFY_USERNAME(기본 "일정관리봇") · $SLACK_NOTIFY_ICON

stdout: 성공 시 `BRIEFING_DM_TS=<ts>` 와 (가능하면) `BRIEFING_DM_LINK=<permalink>`.
종료코드: 0 성공 / 1 실패(토큰·대상·본문 없음, API 거부). 러너가 이 코드로 성공/실패를
판정하므로 여기서 거짓 성공을 내면 안 된다.
"""
import json
import os
import re
import sys
import urllib.request

CFG_DIR = os.path.expanduser("~/.config/calendar-worklog")
BOT_NAME = os.environ.get("SLACK_NOTIFY_USERNAME", "일정관리봇")
BOT_ICON = os.environ.get("SLACK_NOTIFY_ICON", ":spiral_calendar_pad:")


def read_token():
    t = os.environ.get("SLACK_BOT_TOKEN")
    if t:
        return t.strip()
    p = os.path.join(CFG_DIR, "slack-bot-token")
    if os.path.exists(p):
        return open(p).read().strip()
    return None


def read_target(cli_to):
    if cli_to:
        return cli_to
    t = os.environ.get("SLACK_NOTIFY_TARGET")
    if t:
        return t
    p = os.path.join(CFG_DIR, "user-config.yaml")
    if os.path.exists(p):
        m = re.search(r"slack_user_id:\s*['\"]?([A-Z0-9]+)", open(p).read())
        if m:
            return m.group(1)
    return None


def api(token, method, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    args = sys.argv[1:]
    to = None
    if "--to" in args:
        i = args.index("--to")
        to = args[i + 1]
        del args[i:i + 2]

    text = sys.stdin.read().strip()
    if not text:
        sys.exit("send-dm: 본문이 비어 있음 (stdin)")

    token = read_token()
    if not token:
        sys.exit("send-dm: Slack 토큰 없음 (SLACK_BOT_TOKEN 또는 "
                 f"{CFG_DIR}/slack-bot-token)")
    target = read_target(to)
    if not target:
        sys.exit("send-dm: 대상 없음 (--to, SLACK_NOTIFY_TARGET, "
                 "또는 user-config.yaml slack_user_id)")

    try:
        resp = api(token, "chat.postMessage", {
            "channel": target, "text": text,
            "username": BOT_NAME, "icon_emoji": BOT_ICON,
            "unfurl_links": False, "unfurl_media": False,
        })
    except Exception as e:
        sys.exit(f"send-dm: Slack API 호출 실패 — {e}")
    if not resp.get("ok"):
        sys.exit(f"send-dm: Slack 거부 — {resp.get('error')}")

    ts = resp.get("ts")
    channel = resp.get("channel")
    print(f"BRIEFING_DM_TS={ts}")
    # permalink 는 있으면 좋고 없어도 성공엔 무관 — 실패해도 삼킨다.
    try:
        pl = api(token, "chat.getPermalink", {"channel": channel, "message_ts": ts})
        if pl.get("ok") and pl.get("permalink"):
            print(f"BRIEFING_DM_LINK={pl['permalink']}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
