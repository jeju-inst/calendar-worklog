# calendar-worklog-ji (Claude Code 플러그인)

제주연구원(JI) 내부용. 본인 캘린더 4종(과제/근태/업무/기타)에
Slack/monday/AI 활동을 종합해 사후 업무일지를 기록한다.

## 무엇이 되나

- `/worklog late 0835` — 지참 빠른 등록
- `/worklog day` — 어제 일정 자동 정리 (계획 표 → 확인 → 등록)
- `/worklog day 5/30` — 특정 일자 정리
- `/worklog week` — 이번 주 과제 보고 (실 → 구성원 → 과제 트리)
- `/worklog now <제목 날짜 시간>` — 단일 일정 즉시 등록
- `/worklog setup` — 셋업 마법사 (최초 1회)

자유 발화도 OK: `지참 0835`, `어제 정리`, `이번 주 보고` 등.

## 의존성 (requirements)

### 필수 (없으면 동작 자체가 어려움)

| 항목 | 어떻게 | 용도 |
|---|---|---|
| **Claude Code** + Pro/Max 구독 | <https://claude.com/code> | 본 플러그인 호스트 |
| **Google Calendar MCP** | claude.ai 커넥터 토글 (가장 쉬움) 또는 로컬 MCP | 캘린더 읽기/쓰기 |
| **Slack MCP** | claude.ai 커넥터 또는 `/plugin install slack@claude-plugins-official` | 메시지 검색 |
| **monday.com MCP** | claude.ai 커넥터 (admin이 워크스페이스 허용 필요) 또는 로컬 MCP | 보드 활동 조회 |

### 권장 (있으면 활동 커버리지 95%→100%)

| 항목 | 어떻게 | 용도 |
|---|---|---|
| **`mail` 스킬** | 퍼블릭: <https://github.com/z0nam/mail-skill> · 개인정보 포함 변형: <https://github.com/z0nam/mail-skill-namun>. 클론 후 `ln -s <repo>/.claude/skills/mail ~/.claude/skills/mail` | 메일 활동(공식 응대·외부 트래픽) 포함 |
| **Codex CLI** | `brew install codex` 또는 `npm i -g @openai/codex` | Codex 세션 로그 검색 (`~/.codex/history.jsonl`) |
| **Antigravity CLI 사용 기록** | `~/.gemini/antigravity-cli/brain/` 존재 여부 | Antigravity 세션 로그 검색 (`transcript.jsonl`) |
| **Bash + Python 3** | macOS/Linux 기본 포함 | Claude Code·Codex·Antigravity 로컬 세션 로그 스캔 |

## 설치 (동료용)

### 1. 위 필수 의존성 먼저 확보 (커넥터 / MCP 토글)

### 2. 플러그인 설치

```
/plugin marketplace add z0nam/calendar-worklog
/plugin install calendar-worklog-ji
```

### 3. 셋업 마법사 1회 실행

```
/worklog setup
```

마법사가:
- 의존성 점검 (필수/권장 항목 가용 여부 보고)
- 본인 Slack ID (이메일로 조회) · 캘린더 4종 (이름 매칭) · 전사 공식 일정 캘린더 · monday 즐겨찾기 보드 자동 매칭
- 수동 입력은 출퇴근 시각 정도

결과: `~/.config/calendar-worklog/user-config.yaml`

### 4. 시작

```
/worklog late 0835
/worklog day
```

## 어디에 저장되나

- 본인 설정: `~/.config/calendar-worklog/user-config.yaml` (비밀, git에 올리지 말 것)
- 플러그인 본체: `~/.claude/plugins/cache/...` (자동 관리)

## 안전장치

- 이벤트 만들기 전 표로 계획 제시 → 사용자 확인 필요
- 민감 키워드는 일반화 제목으로 자동 치환
- 캘린더는 공개 노출 전제 — DM 본문/AI 세션 본문 그대로 옮기지 않음
- work_hours 밖 활동 자동 등록 금지

## 문제가 있으면

저장소: <https://github.com/z0nam/calendar-worklog>
