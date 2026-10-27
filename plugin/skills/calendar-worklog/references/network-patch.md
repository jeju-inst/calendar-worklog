# JRI 사내망 구글 API 지연 우회

> 로컬에서 Google API를 직접 호출하는 Python 스크립트를 새로 쓰거나 고칠 때만 읽는다. MCP 커넥터로 캘린더를 쓸 때는 해당 없음.

## 네트워크 연결 및 지연 문제 해결 (JRI 사내망 우회)

제주연구원(JRI) 사내망 또는 특정 VPN 환경에서 Google API 호출 시, 일부 googleapis Anycast IP(예: `216.239.36.223`)와 IPv6 라우팅이 차단되어 API가 60초 이상 응답하지 않고 타임아웃이 발생하는 고질적인 문제가 있습니다.

이를 해결하기 위해 로컬에서 Google API를 직접 호출하는 Python 스크립트 작성 시, 다음 DNS/커넥션 우회 패치를 스크립트 최상단(임포트부)에 적용해야 합니다:

```python
import socket

# JRI 사내망 구글 API 지연 우회 패치
orig_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    res = orig_getaddrinfo(host, port, family, type, proto, flags)
    filtered = []
    for r in res:
        ip = r[4][0]
        # IPv4만 허용하고 차단된 Anycast IP 필터링
        if r[0] == socket.AF_INET and ip != "216.239.36.223":
            filtered.append(r)
    return filtered if filtered else res
socket.getaddrinfo = patched_getaddrinfo

orig_connect = socket.socket.connect
def patched_connect(self, address):
    host, port = address
    if isinstance(host, str) and not host.replace('.', '').isdigit():
        try:
            ips = socket.getaddrinfo(host, port)
            if ips:
                target_addr = ips[0][4]
                return orig_connect(self, target_addr)
        except Exception:
            pass
    return orig_connect(self, address)
socket.socket.connect = patched_connect
```

이 패치는 `google_dns_patch.py`로 모듈화되어 있으며, 현재 `calendar-worklog` 및 `ji-calendar-provision` 리포지토리의 주요 구글 캘린더 통신 스크립트(`read_calendars.py`, `add_event.py` 등)의 시작 지점에 자동으로 주입/적용되어 작동하고 있습니다.
