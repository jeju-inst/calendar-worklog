# 트랙별 기능 비교표

calendar-worklog를 돌릴 수 있는 트랙(AI 환경)별 비교입니다. 셋업 전 참고하세요.

## 요약

| 트랙 | 셋업 비용 | 플랜 요건 | 무료 가능 | 주 대상 |
|---|---|---|---|---|
| **Claude Projects** | ~5분 | Claude Pro/Max/Team/Ent | ❌ | 비개발 다수 |
| **ChatGPT Apps / Connectors** | ~10분 | **Plus+ 필요** (Free엔 Google Calendar 커넥터 없음) / Business+ 조직 배포 | ❌ (2026-05-29 확정) | 비개발 다수 |
| **Claude Code** | ~10분 | Claude Pro/Max 또는 API | ❌ | 코드 사용자 |
| **Codex CLI/App** | 10분+ | Plus+ 권장, Free는 기간 한정 가능 | ⚠️ 기간 한정 | 코드/운영자 |

## 능력 비교

| 능력 | Claude Projects | ChatGPT | Claude Code | Codex |
|---|---|---|---|---|
| 캘린더 읽기/쓰기 | ✅ 커넥터 | ⚠️ Plus+만 가능 (Free엔 Google Calendar 커넥터 자체가 없음, 2026-05-29 확정) | ✅ 커넥터/MCP | ✅ 커넥터 (검증됨) |
| Slack 메시지 검색 | ✅ | ⚠️ 공식 Slack app은 paid ChatGPT plan 필요 | ✅ | ✅ 커넥터 (검증됨) |
| monday 활동 조회 | ✅ | ⚠️ Apps 디렉터리/조직 설정/플랜 검증 필요 | ✅ MCP | ✅ 커넥터 (검증됨, 도구 명시 필요) |
| email 조회 | 도구 설정 시 가능 | ⚠️ Gmail/Outlook Apps 가능, 플랜/조직 설정 검증 필요 | MCP 설정 시 가능 | ✅ 커넥터 (gmail) |
| AI 세션 활동 조회 | ✅ (Claude 자체 대화) | ⚠️ ChatGPT search/memory/project memory는 보조 소스 | ✅ Claude 자체 + 로컬 Claude Code·Codex·Antigravity 로그 | ✅ 로컬 Claude Code·Codex·Antigravity 로그 |
| 셋업 난도 | 낮음 | 중 | 중 | 중 (앱은 커넥터 토글) |
| 자동 실행(cron/CI) | ❌ | ❌ | ✅ | ✅ |

## 메모

- **코드 트랙의 AI 세션 수집**은 현재 실행 중인 에이전트만 보지 않고, 로컬에 존재하는
  Claude Code·Codex·Antigravity 로그 세 종류를 각각 확인한다. 채팅창 트랙은 로컬 파일에
  접근할 수 없어 해당 서비스가 제공하는 자체 대화 검색만 사용한다.
- **무료 가능 여부(ChatGPT) — 2026-05-29 확정: 불가.** 동일 기계 A/B 테스트(무료 계정 vs Plus): 무료 계정은 `설정→앱`에 커넥터 목록이 없고 앱 디렉터리에도 **Google Calendar가 안 뜬다**. Plus 계정은 같은 화면에 Google Calendar(✓)/Slack/monday가 뜬다. → 무료엔 Google Calendar 커넥터가 없어 **캘린더 쓰기 자체가 불가 = worklog 핵심 기능 불가**. (이전 '무료에서 Slack 읽기' 실관찰은 이 무료 계정에선 재현 안 됨 — 시점/롤아웃 차이로 추정. Calendar가 막혀 결론은 어차피 불가.) **동료 배포는 Plus+ 전제.**
- **ChatGPT 권장 하한**: 라이트 유저 end-to-end 검증은 Plus부터 보는 것이 현실적이다. 조직 배포와 write action 통제는 Business/Enterprise/Edu가 더 적합하다.
- **자동 매일 실행**(Phase 2)은 코드 트랙(Claude Code/Codex)에서만 구성 가능.
- 데이터 소스(monday·Slack)는 회사가 유료 제공하더라도 ChatGPT app 사용 가능 여부는 OpenAI 플랜/조직 설정의 영향을 받는다.
- **Codex 트랙 end-to-end 검증 완료(2026-05-29)**: 캘린더 읽기/쓰기(생성→재조회→삭제, colorId 기본색 준수), Slack 본인 메시지 검색, monday board activity 본인 활동 추출까지 실데이터로 확인. Codex 앱은 OpenAI 큐레이티드 플러그인 커넥터 방식(npx 불필요). 단 monday는 sprint/dev 도구로 빠지지 않게 `user context → board activity → updates` 순으로 **도구를 명시**해야 안정적(→ prompt.md 단계 C-3, AGENTS.md에 반영).
