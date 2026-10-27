# 워크플로 0 — 셋업 마법사

> `SKILL.md`의 설정 로드·공통 출력 규칙·보안/프라이버시·실패 처리를 그대로 적용한 상태에서 따른다. 이 파일은 해당 워크플로에 들어왔을 때만 읽는다.

## 워크플로 0: 셋업 마법사 (`/worklog setup`)

**목적**: 컴맹도 가능한 1회성 설정 생성. 결과 파일은 `~/.config/calendar-worklog/user-config.yaml`.

### 0-A. 사전 점검

**A-1. 의존성 점검 (아래 표 기준. 설치 안내는 플러그인 README 참조):**

먼저 다음을 확인해 한 줄짜리 표로 보고. **필수 항목이 빠지면 아래 A-1-1(연결 유도)로 간다.** 연결되기 전에는 0-B로 넘어가지 않는다.
해당 도구가 아예 보이지 않으면 호출할 대상이 없으므로 "없음"으로 적습니다.
캘린더 **쓰기** 권한은 이벤트를 만들어 시험하지 말고, 캘린더 목록의 접근 권한(`accessRole`이
`owner` 또는 `writer`)으로 확인합니다.

| 분류 | 항목 | 점검 방법 |
|---|---|---|
| 필수 | Google Calendar MCP | `list_calendars` 호출 가능 여부 |
| 필수 | Slack MCP | `slack_search_users` 호출 가능 여부 |
| 필수 | monday.com MCP | `get_user_context` 호출 가능 여부 |
| 권장 | `mail` 스킬 | `~/.claude/skills/mail/SKILL.md` 존재 여부 |
| 권장 | Codex CLI | `~/.codex/history.jsonl` 존재 여부 |
| 권장 | Claude Code 세션 로그 | `~/.claude/projects/` 존재 + Bash/Python 가용 |
| 권장 | Antigravity 세션 로그 | `~/.gemini/antigravity-cli/brain/` 존재 + Bash/Python 가용 |

권장 항목이 빠지면 해당 소스를 워크플로 2 단계 C(`references/day.md`)에서 건너뛰고 보고에 명시.

**A-1-1. 연결이 없을 때 — 중단하지 말고 연결을 유도:**

0-A에서 빠진 능력이 있으면 바로 끝내지 말고, 사용자가 연결을 마치도록 돕습니다.
원칙은 **각 AI 회사가 직접 제공하는 커넥터(앱)가 1순위**이고, CLI로 MCP 서버를 직접 등록하는 건
그게 실제로 되는 서비스에만 씁니다. 셸이 없는 채팅 환경에서는 1)의 설정 경로만 안내합니다.

**1) 지금 어느 계정 환경인지 판단** (쓸 수 있는 도구 이름으로 추정합니다)

| 단서 | 1순위 연결 경로 |
|---|---|
| `mcp__claude_ai_…` 도구가 보이거나 Claude Code·claude.ai | claude.ai → 설정 → 커넥터에서 Google Calendar·Slack·monday.com 연결. 같은 계정이면 Claude Code에도 자동으로 붙음 |
| `mcp__codex_apps__…` 도구가 보이거나 Codex·ChatGPT | chatgpt.com → 설정 → 앱에서 세 개 연결. Codex CLI도 같은 ChatGPT 계정이면 자동으로 붙음(`codex login status`가 "Logged in using ChatGPT"인지 확인) |
| 그 밖의 로컬 CLI 에이전트(agy, Gemini CLI 등) | 아래 2)와 3) |

도구가 하나도 보이지 않으면 이름으로는 판단할 수 없으니, **지금 실행 중인 에이전트 종류**로 판단합니다
(Codex면 ChatGPT 계정 앱, Claude Code면 claude.ai 커넥터).

**2) CLI로 직접 등록할 수 있는 것은 monday뿐**

monday MCP(`https://mcp.monday.com/mcp`)는 OAuth 동적 클라이언트 등록을 지원하므로, 어떤 에이전트든
CLI로 등록한 뒤 브라우저 로그인만 하면 됩니다. 셸 명령을 실행할 수 있으면 **사용자에게 한 번
확인받고 직접 실행**하십시오. 1)의 커넥터로 이미 monday가 붙어 있으면 중복이므로 등록하지 않습니다.

**이미 등록돼 있는데 monday 도구가 보이지 않으면 로그인만 안 된 상태**입니다(예: `codex mcp list`의 Auth 칸이
`Not logged in`). 다시 등록하지 말고 아래 표의 로그인 명령만 안내합니다. 등록 여부를 확인할 수 없으면
(셸이 안 되는 등) 등록 명령에 "미등록이 확인된 경우에만"이라는 조건을 붙여 안내합니다.

| 에이전트 | 등록 | 로그인(브라우저, 사용자가 직접 승인) |
|---|---|---|
| Claude Code | `claude mcp add --transport http -s user monday https://mcp.monday.com/mcp` | 세션에서 `/mcp` → monday 인증 |
| Codex | `codex mcp add monday --url https://mcp.monday.com/mcp` | 등록 직후 로그인이 자동으로 시작됨. 끊겼으면 `codex mcp login monday` |
| Gemini CLI | `gemini mcp add -t http -s user monday https://mcp.monday.com/mcp` | 세션에서 `/mcp auth monday` (미검증) |
| agy | `agy mcp add monday https://mcp.monday.com/mcp` | 에이전트 실행 시 안내를 따름 (미검증) |

Codex의 `mcp add`는 등록 직후 브라우저 승인을 기다리므로 비대화형 실행에서는 멈춘 것처럼 보입니다.
등록 자체는 이미 끝난 상태이니, 사용자가 브라우저에서 승인하면 됩니다.

**3) Google Calendar와 Slack은 CLI로 직접 등록할 수 없습니다**

두 서비스의 공식 MCP는 OAuth 동적 클라이언트 등록을 지원하지 않고, 미리 발급된 OAuth 클라이언트
(client secret)를 요구합니다(실측 2026-09-11). 그래서 `mcp add --url`로 등록해도 로그인 단계에서
막힙니다. 1)의 AI 회사 커넥터로 연결하도록 안내하십시오. 그런 경로가 없는 에이전트라면
"이 에이전트에서는 캘린더 연결이 어렵다. Claude 또는 ChatGPT(Codex) 계정으로 진행하라"고 사실대로
알립니다. **연결 없이 캘린더 ID 등을 지어내서 진행하지 마십시오.**

**4) 연결을 마친 뒤**

OAuth 승인은 사용자가 브라우저에서 직접 해야 합니다(대신 할 수 없음). 새 연결은 보통 에이전트를
다시 시작해야 도구로 나타나므로, **재시작 후 `셋업`을 다시 입력하라**고 안내하고 이번 실행은 여기서
멈춥니다.

**A-2. 디렉토리 준비:**
- `~/.config/calendar-worklog/` 디렉토리 없으면 만든다 (Bash `mkdir -p`).
- 기존 파일이 있으면 "기존 설정이 있다. 덮어쓸까?"로 확인 후 진행. 백업본 `.bak`으로 보관.

### 0-B. 자동 수집 (사용자에게 묻지 않고 먼저 시도)

가능한 한 자동으로 채우고, 자동 매칭 실패한 항목만 사용자에게 묻는다.

1. **본인 식별** — 사용자 이메일을 ① 캘린더 프로필 또는 기본(primary) 캘린더 ID(= 계정 이메일)
   ② `git config user.email` 순서로 얻는다. 둘 다 없으면 1회만 묻는다.
   - Slack: `slack_search_users(query=email)`로 `slack_user_id` 자동 매칭.
   - 매칭 실패 시 사용자에게 1회만 묻는다.
2. **캘린더 4종** — `list_calendars` 호출.
   - summary에 `[과제]`/`[근태]`/`[업무]`/`[기타]` 또는 `과제`/`근태`/`업무`/`기타`
     키워드가 포함된 캘린더를 자동 매칭.
   - JI는 `[과제] 이름`, `[근태] 이름` 같은 prefix 패턴.
   - 4개 중 일부만 매칭되면 못 찾은 캘린더만 후보 목록(전체 list_calendars 결과)에서 고르게.
3. **전사 공유 캘린더** — `calendar@ji.re.kr` 또는 "제주연구원 공식 일정"이 list_calendars에
   있으면 `read_only_calendars`에 자동 등록.
   이름과 달리 실제 권한과는 무관합니다. 소유·편집 권한이 있더라도 **이 워크플로에서는 쓰지 않고
   점유 시간표에만** 씁니다.
4. **monday 보드** — 다음 4개를 자동 매칭:
   - "진행업무보드" → `favorite_boards`
   - "진행과제보드" → `favorite_boards`
   - "전체 과제리스트" → `favorite_boards`
   - "연구자 소속 마스터" → `organization.monday_roster.board_id`
   - **1차 — 보드 검색**: 이름으로 검색하되 **제목이 정확히 일치하는 결과만** 채택합니다.
     비슷한 이름을 대신 쓰지 마십시오(예: "진행업무보드" 검색에 "진행과제보드"가 나와도 그건 다른 보드).
   - **2차 — 워크스페이스 목록 (1차에서 못 찾은 이름만)**: monday 보드 검색은 **존재하는 보드를
     누락할 수 있습니다** (실측 2026-09-11: 대상 4개 중 "진행업무보드"·"전체 과제리스트" 2개가 정확한 이름
     검색에 나오지 않음. 워크스페이스 목록으로는 4개 모두 `제주연구원_홈`에서 확인됨).
     못 찾았다고 결론 내기 전에 워크스페이스 목록을 받아 워크스페이스별 보드 목록
     (`workspace_info` 등)에서 제목을 정확매칭합니다. 이미 찾은 보드가 속한 워크스페이스
     (JI는 대부분 `제주연구원_홈`)부터 봅니다.
   - 2차까지 실패한 이름만 사용자에게 묻습니다.
5. **명부 보드 컬럼 자동 추출** — 매칭된 명부 보드(`연구자 소속 마스터`)의 컬럼 메타데이터를
   `get_board_info` 또는 GraphQL로 조회.
   - 타입이 `dropdown`이고 제목에 "소속"/"실" → `division_column`
   - 타입이 `dropdown`이고 제목에 "역할" → `role_column`
   - 타입이 `color`/`status`이고 제목에 "부서장"/"상태" → `head_status_column`
   - 타입이 `multiple-person` → `person_column`
   - 매칭 실패 컬럼은 후보 목록 보여주고 고르게.
6. **target_divisions / heads** — 명부 보드 item을 조회해 부서장 status로 마킹된 사람을
   추출. `target_divisions`는 사용자가 보고 대상 실을 1개 이상 고를 수 있게 묻는다.

### 0-C. 사용자에게 묻는 항목 (최소화)

자동 수집 실패분만 묻는다. 추가로 다음만 묻는다:

1. **work_hours** — 기본값 제시: "출근 09:00, 퇴근 18:00로 할까요? 아니면 시간만 알려주세요."
   - JI 표준 근무시간은 09:00~18:00. 그대로 가는 경우가 다수이고, 시차출퇴근제 등으로
     다른 사람만 별도로 입력.
2. **email 정규화** — 회사가 신·구 도메인을 운영하면 `canonical_domain` 확인.
   기본은 `ji.re.kr`, deprecated는 `[jri.re.kr]`. 사용자가 다른 회사면 안내 후 입력 받음.
3. **sensitivity.title_keywords** — 기본 `["[보안]", "대외비", "비공개"]`. 그대로 갈지 확인.

### 0-D. 결과 미리보기 + 확인

Slack 수집 범위 `data_sources.slack.scope`의 기본값은 `all`(채널+DM)입니다. 사용자가 원할 때만 `public_only`로 둡니다.

채운 YAML 전문(민감값은 마스킹 — 캘린더 ID 끝 8자만 표시)을 보여주고 "이대로 저장할까요?"
물어본다. 사용자 OK → 그대로 Write. 수정 요청 → 반영 후 다시 보여주기.

### 0-E. 저장 + 동작 확인

1. `~/.config/calendar-worklog/user-config.yaml` 작성.
   - macOS/Linux: `chmod 600` 으로 본인만 읽게 한다.
   - **Windows: `chmod` 는 성공한 것처럼 보여도 실제로는 적용되지 않는다**(NTFS ACL).
     퍼미션이 걸렸다고 사용자에게 말하지 말 것. 파일은 사용자 프로필 폴더 안에 있다는 정도만 안내.
     본인만 읽게 하려면 PowerShell에서 `icacls "<파일>" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"`
     로 상속을 끊고 본인 권한만 남깁니다(실측 2026-09-11: ACL이 본인 1건으로 줄고 본인은 계속 읽힘).
     사용자에게 한 번 확인받고 실행합니다.
2. 짧은 동작 확인:
   ```
   설정 저장됨: ~/.config/calendar-worklog/user-config.yaml
   다음 명령으로 시작해보세요:
     /worklog late 0835     ← 지참 등록
     /worklog day            ← 어제 정리
   ```
3. 이 파일은 비밀이 들어 있으니 git에 올리지 말 것을 안내.
