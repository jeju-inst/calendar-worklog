#!/usr/bin/env python3
"""claude 로그인 상태 선제 감시 — claude 를 실행하지 않고 자격증명만 확인한다.

왜 비용 0인가
-------------
로그인이 살아있는지 확인하는 데 claude 를 호출할 필요가 없다. 실제 자격증명(keychain)의
만료시각을 읽으면 된다. 토큰·네트워크·quota 소모 0. launchd 가 자주 돌려도 부담 없다.

신호원 (2026-08-03 정정)
------------------------
초판은 `~/.claude/daemon-auth-status.json` 을 봤는데, 이 파일은 **부정확했다** — 실제로
/login 을 다시 해서 keychain 토큰이 갱신됐는데도 이 파일은 `auth_required` 로 낡아 있었다
(claude 데몬이 상태를 늦게 갱신). 그대로 두면 로그인이 멀쩡한데 "풀렸다"고 오탐한다.

그래서 **진짜 자격증명인 keychain 의 refreshTokenExpiresAt 을 1순위로** 본다.
- refreshTokenExpiresAt 이 미래  → 로그인 유효 (access token 은 이걸로 자동 갱신됨)
- refreshTokenExpiresAt 이 과거  → 재로그인 필요 (여기서 알림)
keychain 을 못 읽으면(launchd 권한 등) daemon-auth-status.json 으로 폴백한다.

폐기(revoke) 보강 (2026-08-04)
------------------------------
만료시각은 토큰의 *나이*만 말해준다. 만료 전에 서버에서 폐기되면 keychain 엔 미래
시각이 그대로 남아 있는데 실제 인증은 실패한다 — 위 규칙만으로는 조용히 지나간다.

그렇다고 데몬 파일을 다시 신뢰하면 위에 적은 오탐이 되돌아온다. 그래서 **증명 가능한
시간 순서일 때만** 데몬의 실패 신호를 받아들인다:

    mint(발급시각) < expiresAt (access token 만료시각)  ← 항상 참
    daemon.since >= expiresAt  ⟹  daemon.since > mint   ← 실패가 현재 토큰보다 최신

즉 `daemon.since >= expiresAt` 이면 그 인증 실패는 지금 keychain 에 있는 토큰이 발급된
*뒤*에 일어난 것이 확정된다 → 폐기 의심으로 알린다. 반대로 재로그인을 했다면 access
token 이 새로 발급돼 expiresAt 이 낡은 since 보다 미래가 되므로, **낡은 데몬 파일로는
절대 오탐하지 않는다.** (access token 수명이 짧아 실제 폐기는 몇 시간 안에 잡힌다.
매시간 도는 체크에는 충분하고, 수명 상수를 추측할 필요가 없다는 게 이 규칙의 요점.)

로그인이 풀리면 briefing/notify.py 로 독립 알림(Slack Bot Token 직접, claude 무관)을
보낸다. 상태가 바뀔 때만 1회 알린다(마커로 중복 방지). 복구도 1회 알려 재로그인이
반영됐는지 폰으로 확인할 수 있게 한다.
"""
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
STATUS_FILE = os.path.join(HOME, ".claude", "daemon-auth-status.json")
MARKER = os.path.join(HOME, ".config", "calendar-worklog", ".authcheck-last")
NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.py")
KEYCHAIN_SERVICE = "Claude Code-credentials"


def keychain_state():
    """keychain 기준. ('ok'|'expired', refresh만료ms, access만료ms) 또는 None(못읽음)."""
    try:
        p = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10)
        if p.returncode != 0 or not p.stdout.strip():
            return None
        oauth = json.loads(p.stdout).get("claudeAiOauth", {})
        exp = oauth.get("refreshTokenExpiresAt")
        if not exp:
            return None
        now_ms = time.time() * 1000
        access_exp = oauth.get("expiresAt")
        access_exp = int(access_exp) if access_exp else None
        return ("ok" if exp > now_ms else "expired"), int(exp), access_exp
    except Exception:
        return None


def daemon_state():
    """폴백: 데몬 상태 파일. ('ok'|'expired'|'unknown', since_ms|None)."""
    try:
        d = json.load(open(STATUS_FILE))
        st = str(d.get("status", "unknown"))
        since = d.get("since")
        since = int(since) if isinstance(since, (int, float)) else None
        return ("expired" if st == "auth_required" else "ok"), since
    except Exception:
        return "unknown", None


def resolve():
    """(verdict, key) — verdict: 'ok'|'expired'|'revoked'|'unknown'.

    key 는 중복 알림 방지용 문자열(같은 판정이면 같은 값). 'revoked' 는 keychain 은
    유효한데 데몬이 그 토큰 발급 이후 시점의 인증 실패를 보고하는 경우다.
    """
    kc = keychain_state()
    if kc is None:
        # keychain 못 읽음 → 데몬 파일 폴백
        verdict, since = daemon_state()
        return verdict, f"dm:{verdict}:{since or ''}"

    verdict, exp, access_exp = kc
    if verdict == "ok" and access_exp:
        dv, since = daemon_state()
        # since >= access_exp 여야만 "실패가 현재 토큰보다 최신"이 증명된다.
        # (재로그인했다면 access_exp 가 낡은 since 보다 미래 → 여기 안 걸린다.)
        if dv == "expired" and since is not None and since >= access_exp:
            return "revoked", f"kc:revoked:{since}"
    return verdict, f"kc:{verdict}:{exp}"


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
    except Exception as e:
        sys.stderr.write(f"authcheck: 알림 실패 — {e}\n")


def main():
    verdict, key = resolve()
    prev = last_marker()
    # 마커 형식 "kc:ok:..." / "dm:expired:..." → 가운데가 판정
    prev_verdict = prev.split(":")[1] if prev.count(":") >= 1 else ""

    if key == prev:
        return                          # 같은 판정 그대로 — 조용히 종료

    if verdict == "expired":
        notify("🔴 claude 로그인 만료 감지 — claude 를 쓰는 루틴(아침 브리핑 등)이 멈춥니다. "
               "터미널에서 `claude` 실행 후 재로그인(/login) 필요.")
        save_marker(key)
    elif verdict == "revoked":
        notify("🔴 claude 인증 실패 감지 — 토큰 만료일은 남았지만 폐기된 것으로 보입니다"
               "(현재 토큰 발급 이후 시점의 인증 실패). claude 를 쓰는 루틴이 멈춥니다. "
               "터미널에서 `claude` 실행 후 재로그인(/login) 필요.")
        save_marker(key)
    elif verdict == "ok" and prev_verdict in ("expired", "revoked"):
        notify("🟢 claude 로그인 복구됨. 루틴 정상화.")
        save_marker(key)
    else:
        # ok→ok(값만 변경), unknown 등: 알리지 않고 마커만 갱신
        save_marker(key)


if __name__ == "__main__":
    main()
