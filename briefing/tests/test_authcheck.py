"""authcheck 회귀 테스트 (#47). 실제 keychain·Slack·마커를 건드리지 않는다.

실행: python3 -m unittest discover -s briefing/tests
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "authcheck", os.path.join(HERE, "..", "authcheck.py"))
authcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authcheck)

HOUR_MS = 3600 * 1000


def now_ms():
    return int(time.time() * 1000)


def kc_proc(refresh_exp, access_exp=None, rc=0):
    body = json.dumps({"claudeAiOauth": {
        "refreshTokenExpiresAt": refresh_exp, "expiresAt": access_exp}})
    return subprocess.CompletedProcess([], rc, stdout=body if rc == 0 else "", stderr="")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.patches = [
            mock.patch.object(authcheck, "STATUS_FILE", os.path.join(d, "daemon.json")),
            mock.patch.object(authcheck, "MARKER", os.path.join(d, "cfg", ".authcheck-last")),
            mock.patch.object(authcheck, "UNKNOWN_STATE", os.path.join(d, "cfg", ".authcheck-unknown")),
            mock.patch.object(authcheck, "log", lambda m: None),
        ]
        for p in self.patches:
            p.start()
        self.sent = []
        self.notify_ok = True

        def fake_notify(msg):
            self.sent.append(msg)
            return self.notify_ok
        self.np = mock.patch.object(authcheck, "notify", fake_notify)
        self.np.start()
        self.kc = None  # CompletedProcess 또는 예외

    def tearDown(self):
        self.np.stop()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def daemon(self, status, since):
        with open(authcheck.STATUS_FILE, "w") as f:
            json.dump({"status": status, "since": since}, f)

    def set_marker(self, v):
        os.makedirs(os.path.dirname(authcheck.MARKER), exist_ok=True)
        with open(authcheck.MARKER, "w") as f:
            f.write(v)

    def marker(self):
        try:
            with open(authcheck.MARKER) as f:
                return f.read()
        except FileNotFoundError:
            return None

    def run_main(self):
        def fake_run(*a, **k):
            if isinstance(self.kc, Exception):
                raise self.kc
            return self.kc
        with mock.patch.object(authcheck.subprocess, "run", fake_run):
            authcheck.main()


class KeychainUnreadable(Base):
    def setUp(self):
        super().setUp()
        self.kc = subprocess.CompletedProcess([], 36, stdout="", stderr="")

    def test_stale_auth_required_no_expiry_alert(self):
        # 11/19 사례: keychain 실패 + 8월부터 낡은 auth_required
        self.daemon("auth_required", now_ms() - 100 * 24 * HOUR_MS)
        self.set_marker("kc:ok:123")
        self.run_main()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.marker(), "kc:ok:123")  # 확정 판정 유지

    def test_auth_required_without_since_is_unknown(self):
        self.daemon("auth_required", None)
        v, key, reason = self._resolve()
        self.assertEqual(v, "unknown")
        self.assertIn("security-rc=36", reason)
        self.assertIn("stale:no-since", reason)

    def test_fresh_auth_required_alerts_expired(self):
        self.daemon("auth_required", now_ms() - HOUR_MS)
        self.set_marker("kc:ok:123")
        self.run_main()
        self.assertEqual(self.sent, [authcheck.MSG_EXPIRED])
        self.assertTrue(self.marker().startswith("dm:expired:"))

    def test_timeout_is_unknown(self):
        self.kc = subprocess.TimeoutExpired("security", 10)
        self.daemon("auth_required", now_ms() - 100 * 24 * HOUR_MS)
        v, _, reason = self._resolve()
        self.assertEqual(v, "unknown")
        self.assertIn("security-timeout", reason)

    def test_daemon_ok_is_still_unknown(self):
        self.daemon("ok", None)
        self.assertEqual(self._resolve()[0], "unknown")

    def test_persistent_unknown_alerts_once_without_saying_expired(self):
        self.daemon("auth_required", now_ms() - 100 * 24 * HOUR_MS)
        for _ in range(authcheck.UNKNOWN_ALERT_AFTER + 2):
            self.run_main()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("감시 불가", self.sent[0])
        self.assertIn("만료 판정 아님", self.sent[0])
        # keychain 복구되면 재개 알림 1회, 로그인 복구 알림은 없음(마커가 ok 였으므로)
        self.kc = kc_proc(now_ms() + 30 * 24 * HOUR_MS)
        self.set_marker(f"kc:ok:{now_ms()}")
        self.sent.clear()
        self.run_main()
        self.assertEqual(self.sent, [authcheck.MSG_UNKNOWN_CLEARED])
        self.assertFalse(os.path.exists(authcheck.UNKNOWN_STATE))

    def _resolve(self):
        with mock.patch.object(authcheck.subprocess, "run",
                               side_effect=self.kc if isinstance(self.kc, Exception) else None,
                               return_value=self.kc):
            return authcheck.resolve()


class KeychainReadable(Base):
    def test_ok_silent(self):
        self.kc = kc_proc(now_ms() + 30 * 24 * HOUR_MS, now_ms() + HOUR_MS)
        self.daemon("auth_required", now_ms() - 100 * 24 * HOUR_MS)  # 낡은 파일 무시
        self.run_main()
        self.assertEqual(self.sent, [])
        self.assertTrue(self.marker().startswith("kc:ok:"))

    def test_real_expiry_alerts(self):
        self.kc = kc_proc(now_ms() - HOUR_MS)
        self.set_marker("kc:ok:1")
        self.run_main()
        self.assertEqual(self.sent, [authcheck.MSG_EXPIRED])
        self.assertTrue(self.marker().startswith("kc:expired:"))

    def test_revoked_when_daemon_failure_newer_than_token(self):
        access = now_ms() - HOUR_MS
        self.kc = kc_proc(now_ms() + 30 * 24 * HOUR_MS, access)
        self.daemon("auth_required", access + 1000)
        self.run_main()
        self.assertEqual(self.sent, [authcheck.MSG_REVOKED])

    def test_recovery_after_expired(self):
        self.kc = kc_proc(now_ms() + 30 * 24 * HOUR_MS)
        self.set_marker("kc:expired:1")
        self.run_main()
        self.assertEqual(self.sent, [authcheck.MSG_RECOVERED])

    def test_failed_notify_keeps_marker_for_retry(self):
        self.kc = kc_proc(now_ms() - HOUR_MS)
        self.set_marker("kc:ok:1")
        self.notify_ok = False
        self.run_main()
        self.assertEqual(self.marker(), "kc:ok:1")
        self.notify_ok = True
        self.run_main()
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.marker().startswith("kc:expired:"))


class NotifyWrapper(unittest.TestCase):
    """notify() 자체: 타임아웃·실패 시 False, 예외를 밖으로 내지 않음."""

    def test_timeout_returns_false(self):
        with mock.patch.object(authcheck.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("x", 60)), \
             mock.patch.object(authcheck, "log"):
            self.assertFalse(authcheck.notify("t"))

    def test_nonzero_returns_false(self):
        cp = subprocess.CompletedProcess([], 1, stdout="", stderr="notify: Slack 거부 — x")
        with mock.patch.object(authcheck.subprocess, "run", return_value=cp), \
             mock.patch.object(authcheck, "log") as lg:
            self.assertFalse(authcheck.notify("t"))
            self.assertIn("Slack 거부", lg.call_args[0][0])

    def test_success(self):
        cp = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        with mock.patch.object(authcheck.subprocess, "run", return_value=cp):
            self.assertTrue(authcheck.notify("t"))


if __name__ == "__main__":
    unittest.main()
