#!/usr/bin/env python3
"""claude 로그인 상태 선제 감시 — claude 를 실행하지 않고 로컬 파일만 읽는다.

왜 비용 0인가
-------------
claude 데몬이 인증 상태를 `~/.claude/daemon-auth-status.json` 에 스스로 기록한다.
그래서 로그인이 살아있는지 확인하는 데 claude 를 호출할 필요가 없다 — 파일 하나를
읽을 뿐이다. 토큰·네트워크·quota 소모 0. launchd 가 자주 돌려도 부담이 없다.

로그인이 풀리면(status=auth_required) briefing/notify.py 로 독립 알림(Slack Bot
Token 직접, claude 무관)을 보낸다. 브리핑 실패(하루 1회, 08:00)를 기다리지 않고
풀리는 즉시 안다.

중복 알림 방지
--------------
auth_required 가 지속되면 매 실행마다 알리는 건 소음이다. 마지막으로 알린 상태를
마커에 저장하고, **상태가 바뀔 때만**(정상→auth_required 전이) 1회 알린다.
복구(정상 전환)도 1회 알려, 재로그인이 반영됐는지 폰으로 확인할 수 있게 한다.
"""
import json
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
STATUS_FILE = os.path.join(HOME, ".claude", "daemon-auth-status.json")
MARKER = os.path.join(HOME, ".config", "calendar-worklog", ".authcheck-last")
NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.py")

# 이 값이면 "로그인 풀림"으로 본다. 모르는 값은 정상으로 간주(오탐 방지) — 로그인
# 재촉 알림은 잘못 울리면 오히려 방해라, 확실한 실패 표시에만 반응한다.
BAD = {"auth_required"}


def current():
    """(status, since) 반환. 파일이 없거나 못 읽으면 ('unknown', '')."""
    try:
        d = json.load(open(STATUS_FILE))
        return str(d.get("status", "unknown")), str(d.get("since", ""))
    except Exception:
        return "unknown", ""


def last_marker():
    try:
        return open(MARKER).read().strip()
    except Exception:
        return ""


def save_marker(key):
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    open(MARKER, "w").write(key)


def notify(msg):
    try:
        subprocess.run([sys.executable, NOTIFY, msg], check=True,
                       capture_output=True, text=True, timeout=30)
        return True
    except Exception as e:
        sys.stderr.write(f"authcheck: 알림 실패 — {e}\n")
        return False


def main():
    status, since = current()
    key = f"{status}|{since}"          # 상태+시각. 같은 사건은 한 번만 알린다.
    prev = last_marker()
    prev_status = prev.split("|", 1)[0] if prev else ""

    if key == prev:
        return                          # 이미 알린 상태 그대로 — 조용히 종료

    if status in BAD:
        notify("🔴 claude 로그인 풀림(auth_required) 감지 — claude 를 쓰는 루틴(아침 "
               "브리핑 등)이 멈춥니다. 터미널에서 `claude` 실행 후 재로그인(/login) 필요.")
        save_marker(key)
    elif prev_status in BAD and status not in BAD:
        # 풀렸다가 복구됨 — 재로그인이 반영됐다는 확인 알림
        notify(f"🟢 claude 로그인 복구됨(status={status}). 루틴 정상화.")
        save_marker(key)
    else:
        # 정상 → 정상(값만 바뀜) 등: 알리지 않고 마커만 갱신
        save_marker(key)


if __name__ == "__main__":
    main()
