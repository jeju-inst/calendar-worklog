#!/usr/bin/env python3
"""`claude -p --output-format stream-json --verbose` 출력에서 어시스턴트 텍스트를 전부 모은다.

왜 (C-b, 2026-09-30)
-------------------
`claude -p` 의 기본(text) 출력은 **마지막 어시스턴트 메시지만** stdout 에 낸다. 모델이 본문
블록(BRIEFING_DM_START/END)을 낸 뒤 같은 턴에 도구를 하나 더 부르고(9/30 실측: 글로벌
CLAUDE.md 의 `smon done` 완료 사인) 그 결과를 받아 "끝났다" 한 줄을 마지막으로 내면, 러너는
그 한 줄만 받는다 — 본문은 트랜스크립트에는 있는데 stdout 에는 없어 "본문 없음"으로 실패했다.
호출 순서는 모델 재량이라 프롬프트로 막는 건 보조 수단일 뿐이다. 러너가 stream-json 으로 받아
**턴에 상관없이 어시스턴트 텍스트를 전부 이어붙이면** 본문이 어디서 나오든 잡힌다.

입력(stdin): stream-json 줄들. stderr 가 섞여 들어와도 된다 — JSON 이 아닌 줄(인증 에러 문구 등)은
그대로 통과시켜 러너의 실패 원인 grep(OAuth session expired 등)이 계속 동작하게 한다.
출력(stdout): 텍스트만. 러너는 이 출력을 예전 text 모드 OUT 과 똑같이 awk/grep 한다.

- 최상위 어시스턴트 텍스트만 모은다(parent_tool_use_id 가 없는 것). 서브에이전트가 낸 텍스트는
  상태 토큰(BRIEFING_SKIPPED/FAILED)이나 마커를 우연히 흉내 낼 수 있어 제외한다.
- `result` 이벤트의 텍스트는 마지막 어시스턴트 텍스트와 같으므로 평소엔 안 붙인다. 단 에러
  결과(is_error)이거나 어시스턴트 텍스트가 하나도 없으면 붙인다 — 실패 문구가 거기에 온다.
"""
import json
import sys


def main() -> int:
    texts: list[str] = []
    passthrough: list[str] = []
    result_text = ""
    result_is_error = False
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            passthrough.append(line)
            continue
        if not isinstance(ev, dict):
            passthrough.append(line)
            continue
        kind = ev.get("type")
        if kind == "assistant":
            if ev.get("parent_tool_use_id"):
                continue
            content = (ev.get("message") or {}).get("content") or []
            if isinstance(content, str):
                texts.append(content)
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text") or ""
                    if t.strip():
                        texts.append(t)
        elif kind == "result":
            r = ev.get("result")
            if isinstance(r, str):
                result_text = r
            result_is_error = bool(ev.get("is_error"))

    out = list(passthrough)
    out.extend(texts)
    if result_text and (result_is_error or not texts):
        out.append(result_text)
    sys.stdout.write("\n".join(out))
    if out:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
