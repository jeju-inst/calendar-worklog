# 트랙별 셋업 가이드 (전체)

calendar-worklog를 본인 환경에 도입하는 모든 트랙의 단계별 절차.
**본인이 쓰는 AI에 맞는 한 섹션만** 따라가면 됩니다.

> 짧은 1페이지 인트로는 [`onboarding.md`](onboarding.md), 발표용 슬라이드는 [`seminar-intro.md`](seminar-intro.md).

---

## 공통 준비물

- **유료 AI 구독 1종 (필수)**
  - Claude Pro/Max — A·B 가능
  - ChatGPT Plus+ — A 가능
  - Codex(구독·API) — C 가능
  - Claude Pro + Claude Code — D 가능
  - ❌ **무료 ChatGPT는 안 됨** (Google Calendar 커넥터가 없음, 2026-05-29 확정)
  - ❌ **Gemini 트랙은 미검증** (현재 키트에 없음)
- **본인 정보** — 시작 전에 모아두기:
  - Google Calendar 4 캘린더 ID (과제 / 근태 / 업무 / 기타)
  - 본인 Slack `user_id` (Slack 프로필 → "Copy member ID")
  - monday 즐겨찾기 보드 ID들
  - 출퇴근 시간 (요일별 다르면 weekly로 분리)
- **monday AI 커넥터 회사 허용** — 어드민(조남운)이 일괄 처리
- **GitHub 계정** (선택) — 저장소가 Public이라 계정 없어도 clone·다운로드 가능

---

## 어떤 트랙이 나에게?

| 항목 | 채팅창 (A·B) | 코드 도구 (C·D) |
|---|---|---|
| 셋업 시간 | 5분 | 10분+ |
| 비개발자 친화 | ✅ | ❌ (터미널 필요) |
| 매일 아침 자동 실행 (Phase 2 예정) | ❌ | ✅ |
| AI 과거 대화를 활동 소스로 | ChatGPT 보조 검색 / Claude ✅ | Claude Code·Codex·Antigravity 로컬 로그 ✅ |
| `지참 0835` / `어제 정리` / 명시 일정 | ✅ | ✅ |

처음 도입은 **A 또는 B**가 압도적으로 쉽습니다. 자동화/코드 작업이 필요해지면 그때 C·D로.

---

## 공통 1단계 — `user-config.yaml` 만들기

어느 트랙이든 이 파일이 필요합니다.

1. 저장소 클론(또는 다운로드)
   ```bash
   git clone https://github.com/z0nam/calendar-worklog
   cd calendar-worklog
   ```
   (Public이라 GitHub 계정 없이도 됨)
2. 템플릿 복사
   ```bash
   cp core/user-config.example.yaml core/user-config.yaml
   ```
3. 에디터(메모장/VS Code/뭐든)로 `core/user-config.yaml` 열어 본인 값으로 채우기:
   - `user.name` / `slack_user_id` / `timezone`
   - `work_hours` (출퇴근 시각)
   - `calendars.{과제,근태,업무,기타}.id` — Google 캘린더 → 각 캘린더 설정 → "캘린더 통합" → 캘린더 ID 복사
   - `data_sources.monday.favorite_boards` — monday 보드 URL의 `/boards/` 뒤 숫자

> 이 파일은 `.gitignore`에 잡혀 있어 **푸시되지 않습니다** — 개인 로컬 전용.

---

## A. ChatGPT Plus — 채팅창 (가장 쉬움)

### A-1. 데이터 커넥터 연결 (한 번만, 약 2분)
- `chatgpt.com` 로그인 → 우측 상단 **⚙️(톱니)** → **설정 → 앱**
- **Google Calendar / Slack / Monday.com** 각각 클릭 → **Connect** → OAuth 승인
- monday가 목록에 없으면 → 어드민(조남운) 처리 요청

### A-2. Project 만들기 (한 번만, 약 3분)
- 좌측 메뉴 **프로젝트** → **+ 새 프로젝트** → 이름 적당히 (예: `업무기록`)
- **Instructions** 칸: `presets/chatgpt-gpts/instructions.md` 내용을 그대로 복사·붙여넣기
- **Files** 칸: 다음 두 파일을 끌어다 놓기
  - `core/prompt.md`
  - 본인 정보로 채운 `core/user-config.yaml`

### A-3. 동작 확인
- 그 프로젝트 안에서 **새 채팅** → `지참 0835` 입력
- 근태 캘린더에 `08:30~08:35 지참 08:35` 박혔는지 확인 (안 늦었으면 만든 뒤 삭제)

### A-주의사항
- ChatGPT는 긴 채팅에서 Project Files를 다시 안 읽으려는 보수성이 있음 → 잘 안 되면 새 채팅 열거나 채팅에서 calendar_id를 직접 명시
- 무료 ChatGPT는 절대 안 됨 (Google Calendar 커넥터 자체가 없음)

---

## B. Claude Pro — 채팅창 (가장 쉬움)

### B-1. 데이터 커넥터 연결 (한 번만, 약 2분)
- `claude.ai` 로그인 → 우측 상단 **⚙️** → **Settings → Connectors**
- **Google Calendar / Slack / monday.com** 각각 → **Connect** → OAuth 승인

### B-2. Project 만들기 (한 번만, 약 3분)
- 좌측 **Projects** → **New Project** → 이름: `업무기록`
- **Project knowledge** (우측 패널)에 다음 2개 업로드:
  - `core/prompt.md`
  - 본인이 채운 `core/user-config.yaml`

### B-3. 동작 확인
- 프로젝트에서 새 채팅 → `지참 0835` 입력 → 근태 캘린더 확인

### B-강점
- **과거 Claude 대화 검색**을 활동 소스로 추가 활용 가능 (ChatGPT 트랙에 없는 능력)

---

## C. Codex — 데스크톱 앱 (개발자/운영자)

### C-1. Codex 데스크톱 앱 설치 & 로그인
- OpenAI에서 Codex 데스크톱 앱 다운로드 → 설치 → 로그인

### C-2. 플러그인 켜기 (한 번만)
- 앱 내 플러그인/커넥터 패널에서 ON:
  - `google-calendar@openai-curated`
  - `slack@openai-curated`
  - `monday-com@openai-curated`
- 각각 OAuth Connect

### C-3. Codex에서 실행
- Codex 앱에서 calendar-worklog 디렉토리를 작업 디렉토리로 지정
- `AGENTS.md` + `core/prompt.md` + `core/user-config.yaml`이 자동 로드됨
- 채팅에 `지참 0835` → 확인

### C-강점·주의
- **자동화 가능** — 매일 아침 cron으로 "어제 정리" 자동 실행 (Phase 2 예정)
- **monday 도구 선택 주의** — sprint/dev 도구가 아니라 `user context → board activity → updates` 순으로 호출되어야 함 (`AGENTS.md`에 명시됨)
- **2026-05-29 end-to-end 검증 완료** (캘린더 R/W·Slack·monday 모두)

---

## D. Claude Code — CLI (개발자)

### D-1. Claude Code 설치
```bash
npm install -g @anthropic-ai/claude-code
```
또는 VS Code / JetBrains에 Claude Code 확장 설치

### D-2. 커넥터 연결 (한 번만)
- `claude.ai`에서 Google Calendar / Slack / monday Connect
- Claude Code 2.1.46+에 자동 공유됨

### D-3. 실행
```bash
cd calendar-worklog
claude
```
- `CLAUDE.md` + `core/prompt.md` + `core/user-config.yaml` 자동 로드
- `지참 0835` 입력 → 확인

### D-강점
- 본인 PC 파일·스크립트·git을 함께 다룰 수 있어 Phase 2 코드 작업에 적합

---

## 첫 명령 시퀀스 (모든 트랙 공통)

| 입력 | 기능 |
|---|---|
| `지참 0835` | 근태 캘린더에 `08:30~08:35 지참 08:35` 즉시 등록 (워크플로 1) |
| `어제 정리` | Slack/monday/캘린더 종합 → **계획표** → 승인 → 4 캘린더 자동 분류 등록 (워크플로 2) |
| `5월 30일 14시 회의 등록해줘` | 명시 일정 단건 등록 (워크플로 3) |

> 모든 쓰기는 **계획표 → 승인 → 등록** 순서. 마음대로 안 박힘.

---

## 보안 모델 (꼭 알아야 할 것)

- **캘린더는 공개 노출 전제** (`calendar.namun.net` 등이 published) → 캘린더에 기록되는 제목/설명은 외부 노출된다고 보고 작성
- **Blacklist 방식**: 기본 공개 가능. 보안 필요 과업만 제목에 키워드(`[보안]`, `대외비`, `비공개`) 명시 → 키워드 있으면 **일반화 제목만** 기재(`[과제] 내부 검토` 등), description 비움
- monday/Drive/Meet **링크는 OAuth로 접근 통제** → description에 남겨도 무방 (열람 권한자만)
- 애매하면 **사용자에게 확인 요청**(`확인 필요` 마킹), 임의 생성 안 함
- 자세히는 `core/prompt.md`의 "보안/프라이버시" 섹션

---

## 막히면

조남운 (`namun@ji.re.kr` / Slack DM). **화면 캡쳐**와 함께 보내주시면 빠릅니다.
- 흔한 막힘:
  - "Google Calendar Connect 버튼이 안 보임" → 무료 플랜일 가능성 (위 공통 준비물 참고)
  - "지참 0835 했는데 기본 캘린더로 들어감" → 새 채팅에서 다시 + `user-config.yaml의 calendars.근태.id 호출` 명시
  - "monday 안 보임" → 어드민이 회사 AI 커넥터 허용했는지 확인
