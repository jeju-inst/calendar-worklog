# Codex 셋업

Codex 사용자가 calendar-worklog를 돌리는 방법입니다. (코드 트랙)

> **검증 메모(2026-05).** 실제 Codex(데스크톱 앱)는 데이터 소스를 **OpenAI 큐레이티드
> 플러그인 커넥터**로 붙입니다 — Claude 커넥터 / ChatGPT Apps와 같은 OAuth 토글 방식.
> Google Calendar / Slack / monday.com 모두 큐레이티드 플러그인이 **존재**합니다.
> 구버전 핸드오프의 "mcp.json" 또는 "npx로 서드파티 MCP 서버 직접 실행"은 이 경우 불필요.
> npx/커스텀 MCP는 큐레이티드 플러그인이 없는 소스에만 씁니다.

## 사전 조건

- **Codex 데스크톱 앱**(`/Applications/Codex.app`) + OpenAI 인증 (ChatGPT 구독/모델 접근은 별도)
  - CLI(`codex`)도 가능하나, 데이터 소스 연결은 앱 UI에서 하는 게 가장 쉬움
- monday를 쓰면 **회사 어드민이 AI 커넥터 접근을 허용**해 둬야 함

## 1단계: `user-config.yaml` 준비

Claude/ChatGPT 트랙과 **동일한 단일 소스**를 재사용합니다. 이미 만든 파일이 있으면 그대로.

없으면 2~3단계를 먼저 하고 `셋업`이라고 치면 **워크플로 0(셋업 마법사)** 이 커넥터로
캘린더 4종·Slack ID·monday 보드를 조회해 채워 줍니다. Codex는 파일을 쓸 수 있으므로
마법사가 `~/.config/calendar-worklog/user-config.yaml`에 직접 저장합니다.

손으로 쓰려면 `core/user-config.example.yaml`을 복사해 채웁니다.

## 2단계: 커넥터(플러그인) 켜기

Codex 앱의 플러그인/커넥터 목록에서 켜고 OAuth로 연결합니다:

| 소스 | 플러그인 | 비고 |
|---|---|---|
| Google Calendar | `google-calendar@openai-curated` | 이벤트 읽기/쓰기. 필수 |
| Slack | `slack@openai-curated` | 메시지 검색. 강력 권장 |
| monday.com | `monday-com@openai-curated` | 보드 활동/Time Tracking. **어드민 허용 필요** |

- 토글하면 `~/.codex/config.toml`에 `[plugins."...@openai-curated"]` 줄이 기록됩니다.
  수동 편집을 원하면 `presets/codex/config.toml.example` 참조.
- 토글만으로는 부족하고, 각 커넥터의 **OAuth "Connect"를 승인**해야 실제로 호출됩니다.

## 3단계: AGENTS.md 배치

`presets/codex/AGENTS.md`를 작업 디렉토리 루트(또는 전역 `~/.codex/AGENTS.md`)에 둡니다.
같은 디렉토리에 `core/prompt.md` + 본인 `user-config.yaml`을 두면 Codex가 참조합니다.
(`calendar-worklog` repo 디렉토리에서 작업하면 셋이 이미 한곳에 모입니다.)

## 4단계: 동작 확인

```
지참 0835
어제 정리
```
- `지참` → 근태 캘린더에 빠른 등록
- `어제 정리` → 등록 계획 표 출력 → 승인 시 빈 슬롯에 업무 블록 생성
- 쓰기 작업마다 Codex 도구 승인 프롬프트가 뜸 (계획 게이트 + 승인 = 2중 안전장치)

## 메모

- **무료 가능성**: Codex는 모델 접근(구독/API)이 별도 비용이라 ChatGPT 무료 플랜
  검증과는 별개 문제. 커넥터 연결 자체는 토글 방식이라 어렵지 않음.
- Phase 2의 코드 작업(monday Time Tracking 동기화, cron/Actions 자동 실행) 때
  이 트랙을 도그푸딩하기 좋음.

## 참고

- [Model Context Protocol — Codex](https://developers.openai.com/codex/mcp)
- [Configuration Reference — Codex](https://developers.openai.com/codex/config-reference)
- UI/플러그인 식별자는 변동될 수 있으니 앱의 실제 표기를 우선 확인
