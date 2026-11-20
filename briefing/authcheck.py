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

읽기 실패 ≠ 만료 (2026-11-20, #47)
---------------------------------
keychain 을 못 읽을 때 데몬 파일을 그대로 믿으면 8월부터 낡아 있던 `auth_required` 가
그대로 "만료"로 확정돼 오탐한다(2026-11-19 08:22, 재부팅 직전 시스템이 불안정하던 때).
그래서 keychain 을 못 읽으면:
- 데몬의 `auth_required` 는 `since` 가 DAEMON_FRESH_SEC 안일 때만 만료로 받는다.
  그보다 오래됐거나 시각이 없으면 **unknown(확인 불가)** 이다.
- unknown 은 마커를 건드리지 않는다(마지막 확정 판정 유지). 한 번은 조용히 넘기고,
  UNKNOWN_ALERT_AFTER 회 연속이면 "감시 불가" 를 1회 알린다 — 만료라고 말하지 않는다.
- 읽기 실패 사유(종료코드·분류, 비밀정보 없음)를 시각과 함께 stderr(authcheck.err)에 남긴다.

알림이 실패하면 마커를 저장하지 않는다 → 다음 회차에 다시 보낸다. 타임아웃이면
실제로는 도착했을 수 있어 중복 알림이 갈 수 있지만, 진짜 만료 알림을 놓치는 것보다 낫다.

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
UNKNOWN_STATE = os.path.join(HOME, ".config", "calendar-worklog", ".authcheck-unknown")
NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.py")
KEYCHAIN_SERVICE = "Claude Code-credentials"

# keychain 을 못 읽을 때 데몬의 auth_required 를 받아들이는 최대 나이.
# 체크가 매시간이므로 2-3회차 안의 실패만 "최근"으로 본다.
DAEMON_FRESH_SEC = 3 * 3600
# unknown 이 이만큼 연속되면 "감시 불가"를 1회 알린다.
UNKNOWN_ALERT_AFTER = 3
NOTIFY_TIMEOUT = 60

# security(1) 종료코드 → 사람이 읽을 분류. 값 자체는 OSStatus 하위 바이트라 겹칠 수 있어 참고용.
SECURITY_RC = {
    36: "interaction-not-allowed(잠김·GUI 없음)",
    44: "item-not-found",
    51: "auth-failed",
    128: "user-canceled",
}


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    sys.stderr.write(f"[{ts}] authcheck: {msg}\n")


def keychain_state():
    """keychain 기준.

    성공: ('ok'|'expired', refresh만료ms, access만료ms)
    실패: ('unreadable', 사유문자열) — 사유에 비밀정보를 넣지 않는다.
    """
    try:
        p = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return "unreadable", "security-timeout(10s)"
    except Exception as e:
        return "unreadable", f"security-exec:{type(e).__name__}"
    if p.returncode != 0:
        cls = SECURITY_RC.get(p.returncode, "other")
        return "unreadable", f"security-rc={p.returncode}:{cls}"
    if not p.stdout.strip():
        return "unreadable", "empty-secret"
    try:
        data = json.loads(p.stdout)
    except Exception:
        return "unreadable", "json-parse"
    oauth = data.get("claudeAiOauth") if isinstance(data, dict) else None
    if not isinstance(oauth, dict):
        return "unreadable", "no-claudeAiOauth"
    exp = oauth.get("refreshTokenExpiresAt")
    if not exp:
        return "unreadable", "no-refreshTokenExpiresAt"
    try:
        exp = int(exp)
        access_exp = oauth.get("expiresAt")
        access_exp = int(access_exp) if access_exp else None
    except (TypeError, ValueError):
        return "unreadable", "bad-timestamp"
    now_ms = time.time() * 1000
    return ("ok" if exp > now_ms else "expired"), exp, access_exp


def daemon_state():
    """데몬 상태 파일. ('ok'|'expired'|'unknown', since_ms|None)."""
    try:
        with open(STATUS_FILE) as f:
            d = json.load(f)
        st = str(d.get("status", "unknown"))
        since = d.get("since")
        since = int(since) if isinstance(since, (int, float)) else None
        return ("expired" if st == "auth_required" else "ok"), since
    except Exception:
        return "unknown", None


def resolve():
    """(verdict, key, reason) — verdict: 'ok'|'expired'|'revoked'|'unknown'.

    key 는 중복 알림 방지용 문자열(같은 판정이면 같은 값). 'revoked' 는 keychain 은
    유효한데 데몬이 그 토큰 발급 이후 시점의 인증 실패를 보고하는 경우다.
    reason 은 unknown 일 때의 사유(진단용, 비밀정보 없음), 그 외엔 "".
    """
    kc = keychain_state()
    if kc[0] == "unreadable":
        reason = kc[1]
        dv, since = daemon_state()
        now_ms = time.time() * 1000
        if dv == "expired" and since is not None and 0 <= now_ms - since <= DAEMON_FRESH_SEC * 1000:
            # 최근 실패가 증명됨 → keychain 없이도 만료로 받는다.
            return "expired", f"dm:expired:{since}", ""
        if dv == "expired":
            age = "no-since" if since is None else f"{int((now_ms - since) / 3600000)}h"
            reason += f"; daemon=auth_required(stale:{age})"
        else:
            reason += f"; daemon={dv}"
        # 데몬이 ok 라 해도 그건 8월에 틀렸던 신호원이므로 확정하지 않는다.
        return "unknown", "", reason

    verdict, exp, access_exp = kc
    if verdict == "ok" and access_exp:
        dv, since = daemon_state()
        # since >= access_exp 여야만 "실패가 현재 토큰보다 최신"이 증명된다.
        # (재로그인했다면 access_exp 가 낡은 since 보다 미래 → 여기 안 걸린다.)
        if dv == "expired" and since is not None and since >= access_exp:
            return "revoked", f"kc:revoked:{since}", ""
    return verdict, f"kc:{verdict}:{exp}", ""


def last_marker():
    try:
        with open(MARKER) as f:
            return f.read().strip()
    except Exception:
        return ""


def save_marker(key):
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, "w") as f:
        f.write(key)


def load_unknown():
    try:
        with open(UNKNOWN_STATE) as f:
            d = json.load(f)
        return {"count": int(d.get("count", 0)), "alerted": bool(d.get("alerted"))}
    except Exception:
        return {"count": 0, "alerted": False}


def save_unknown(st):
    os.makedirs(os.path.dirname(UNKNOWN_STATE), exist_ok=True)
    with open(UNKNOWN_STATE, "w") as f:
        json.dump(st, f)


def clear_unknown():
    try:
        os.remove(UNKNOWN_STATE)
    except FileNotFoundError:
        pass


def notify(msg):
    """알림 발송. 성공하면 True. 실패 사유는 시각·소요시간과 함께 stderr 에."""
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, NOTIFY, msg],
                           capture_output=True, text=True, timeout=NOTIFY_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"알림 실패 — notify.py {NOTIFY_TIMEOUT}s 타임아웃 "
            "(발송됐을 수도 있음, 다음 회차 재시도): " + msg[:40])
        return False
    except Exception as e:
        log(f"알림 실패 — {type(e).__name__}: {e}")
        return False
    dt = time.time() - t0
    if p.returncode != 0:
        err = (p.stderr or "").strip().splitlines()
        log(f"알림 실패 — rc={p.returncode} {dt:.1f}s: {err[-1] if err else ''}")
        return False
    if dt > 10:
        log(f"알림 지연 — {dt:.1f}s 걸림")
    return True


MSG_EXPIRED = ("🔴 claude 로그인 만료 감지 — claude 를 쓰는 루틴(아침 브리핑 등)이 멈춥니다. "
               "터미널에서 `claude` 실행 후 재로그인(/login) 필요.")
MSG_REVOKED = ("🔴 claude 인증 실패 감지 — 토큰 만료일은 남았지만 폐기된 것으로 보입니다"
               "(현재 토큰 발급 이후 시점의 인증 실패). claude 를 쓰는 루틴이 멈춥니다. "
               "터미널에서 `claude` 실행 후 재로그인(/login) 필요.")
MSG_RECOVERED = "🟢 claude 로그인 복구됨. 루틴 정상화."
MSG_UNKNOWN = ("🟡 claude 로그인 감시 불가 — {n}시간째 자격증명을 읽지 못해 로그인 상태를 "
               "확인할 수 없습니다(만료 판정 아님). 사유: {reason}. "
               "아침 브리핑이 정상이면 무시해도 됩니다.")
MSG_UNKNOWN_CLEARED = "🟢 claude 로그인 감시 재개 — 자격증명을 다시 읽었습니다."


def main():
    verdict, key, reason = resolve()

    if verdict == "unknown":
        # 마지막 확정 판정(마커)은 그대로 둔다 — unknown 으로 덮으면 복구 판단이 꼬인다.
        st = load_unknown()
        st["count"] += 1
        log(f"자격증명 확인 불가 ({st['count']}회 연속): {reason}")
        if st["count"] >= UNKNOWN_ALERT_AFTER and not st["alerted"]:
            if notify(MSG_UNKNOWN.format(n=st["count"], reason=reason)):
                st["alerted"] = True
        save_unknown(st)
        return

    ust = load_unknown()
    if ust["count"]:
        if ust["alerted"] and verdict == "ok":
            if not notify(MSG_UNKNOWN_CLEARED):
                return                  # 다음 회차에 재시도
        clear_unknown()

    prev = last_marker()
    # 마커 형식 "kc:ok:..." / "dm:expired:..." → 가운데가 판정
    prev_verdict = prev.split(":")[1] if prev.count(":") >= 1 else ""

    if key == prev:
        return                          # 같은 판정 그대로 — 조용히 종료

    if verdict == "expired":
        msg = MSG_EXPIRED
    elif verdict == "revoked":
        msg = MSG_REVOKED
    elif verdict == "ok" and prev_verdict in ("expired", "revoked"):
        msg = MSG_RECOVERED
    else:
        msg = None                      # ok→ok(값만 변경): 알리지 않고 마커만 갱신

    if msg is None or notify(msg):
        save_marker(key)
    # 알림 실패 시 마커를 저장하지 않는다 → 다음 회차에 같은 알림 재시도


if __name__ == "__main__":
    main()
