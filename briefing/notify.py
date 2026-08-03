#!/usr/bin/env python3
"""독립 알림 — claude/codex/agy 를 거치지 않고 Slack Bot Token 으로 직접 DM.

왜 이렇게 하나
--------------
루틴(아침 브리핑 등)이 죽는 가장 흔한 원인은 claude 의 OAuth 세션 만료다.
그런데 claude 가 죽으면 claude 경유 Slack MCP 도 같이 죽는다 — 즉 **감시 대상과
알림 경로가 같은 신뢰 도메인이면 알림이 안 나간다.**

그래서 이 스크립트는 어떤 에이전트도 거치지 않는다. Slack Bot Token(xoxb) 으로
Slack Web API(chat.postMessage) 를 직접 호출할 뿐이다. claude/codex/agy 의 로그인
상태와 무관하게 동작한다. 파이썬 표준 라이브러리만 쓴다(외부 의존성 0).

토큰 출처 (우선순위)
  1) 환경변수 SLACK_BOT_TOKEN
  2) ~/.config/calendar-worklog/slack-bot-token  (레포 밖, chmod 600)
대상 (우선순위)
  1) 인자 --to <channel_or_user_id>
  2) 환경변수 SLACK_NOTIFY_TARGET
  3) ~/.config/calendar-worklog/user-config.yaml 의 user.slack_user_id

사용:  notify.py "메시지"  [--to U0XXXX]
종료코드: 0 성공 / 1 실패(토큰·대상 없음, API 오류). 알림이 실패해도 호출측 러너가
그 사실을 로그로 남길 수 있도록 exit code 로 알린다.
"""
import json
import os
import re
import sys
import urllib.request

CFG_DIR = os.path.expanduser("~/.config/calendar-worklog")


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
    # user-config.yaml 에서 slack_user_id 추출 (yaml 의존성 없이 정규식으로)
    p = os.path.join(CFG_DIR, "user-config.yaml")
    if os.path.exists(p):
        m = re.search(r"slack_user_id:\s*['\"]?([A-Z0-9]+)", open(p).read())
        if m:
            return m.group(1)
    return None


def post(token, channel, text):
    body = json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    args = sys.argv[1:]
    to = None
    if "--to" in args:
        i = args.index("--to")
        to = args[i + 1]
        del args[i:i + 2]
    text = " ".join(args).strip()
    if not text:
        sys.exit("notify: 메시지가 비어 있음")

    token = read_token()
    if not token:
        sys.exit("notify: Slack 토큰 없음 (SLACK_BOT_TOKEN 또는 "
                 f"{CFG_DIR}/slack-bot-token)")
    target = read_target(to)
    if not target:
        sys.exit("notify: 대상 없음 (--to, SLACK_NOTIFY_TARGET, "
                 "또는 user-config.yaml slack_user_id)")

    try:
        resp = post(token, target, text)
    except Exception as e:
        sys.exit(f"notify: Slack API 호출 실패 — {e}")
    if not resp.get("ok"):
        sys.exit(f"notify: Slack 거부 — {resp.get('error')}")
    print(f"notify: 발송 완료 (ts={resp.get('ts')})")


if __name__ == "__main__":
    main()
