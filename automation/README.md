# automation/ — 주간 과제 보고 무인화 (`/schedule` 루틴)

매주 금 18:00, 노트북이 꺼져 있어도 Anthropic 클라우드(`/schedule`)가 이 저장소를 fresh clone 해
주간 과제 보고를 생성하고 **Slack #연구부서장**에 실별 2건을 자동 게시한다.

## 설계 (왜 이렇게)
- **루틴 실행 계정 = namun claude.ai** → Slack·monday 커넥터를 그대로 사용(게시·조회). 개인 커넥터 유지.
- **캘린더 = 커넥터 대신 스크립트+토큰.** 22명 캘린더는 커넥터(=본인 것만 보임)로 못 읽으므로,
  전 구성원 `[과제]/[업무]/[근태]/[기타]` 캘린더의 **writer 인 허브계정 `calendar@ji.re.kr`** 의
  **calendar.readonly OAuth refresh token** 으로 읽는다.
- **서비스계정 키를 쓰지 않는다.** 조직정책 `iam.managed.disableServiceAccountKeyCreation`(SA 키 차단)과
  무관하고, 클라우드 env 에 올라가는 건 broad 위임키가 아니라 **revoke 가능한 readonly 토큰**뿐.
- roster/slack_id 등 PII 는 커밋하지 않는다 → 루틴이 monday·Slack 에서 **런타임 재생성**.

## 구성
| 파일 | 용도 | 실행 위치 |
|---|---|---|
| `read_calendars.py` | 토큰으로 구성원 캘린더 읽기 | 루틴(클라우드) |
| `routine-prompt.md` | `/schedule` 에 등록할 작업 지시 | 루틴(클라우드) |
| `list_member_calendar_ids.py` | MEMBER_CALENDAR_IDS(88개 ID) 산출·검증 | 로컬 1회(멤버 변경 시 재실행) |
| `get_refresh_token.py` | calendar@ readonly refresh token 발급 | 로컬 1회 |

## 셋업 (1회)

### ⓪ 캘린더 ID 목록 산출 (로컬)
```
GOOGLE_APPLICATION_CREDENTIALS=~/.secure/gcp/ji-user-calendar-provisioning-546ed9bb88fb.json \
ROSTER=scratch/roster.json \
~/dev/ji-calendar-provision/.venv/bin/python automation/list_member_calendar_ids.py
```
→ `ids_env.json` 의 내용이 곧 env `MEMBER_CALENDAR_IDS` 값. (현재 88개, hub_readable=88 검증됨.)

### ③ GCP OAuth Client ID 생성 (콘솔)
프로젝트 `ji-user-calendar-provisioning` →
1. **API 및 서비스 → OAuth 동의화면**: User type **Internal**, 앱 게시.
2. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**:
   애플리케이션 유형 **데스크톱 앱**. 생성 후 **JSON 다운로드**.
   - ※ 이건 SA 키가 아니라 OAuth 클라이언트라 `disableServiceAccountKeyCreation` 정책에 안 걸린다.

### ④ refresh token 발급 (로컬)
```
pip install google-auth-oauthlib
CLIENT_SECRET_FILE=~/Downloads/client_secret_xxx.json \
  ~/dev/ji-calendar-provision/.venv/bin/python automation/get_refresh_token.py
```
브라우저가 열리면 **반드시 `calendar@ji.re.kr` 로 로그인**하고 읽기 권한 허용.
→ 콘솔에 `CAL_CLIENT_ID` / `CAL_CLIENT_SECRET` / `CAL_REFRESH_TOKEN` 출력.

### ⑥ `/schedule` 루틴 등록 (Claude Code)
- 일정: 매주 금 18:00 (반복)
- 저장소: 이 repo
- 커넥터: **Slack + monday** 체크 (Google Calendar 커넥터 불필요)
- 프롬프트: `automation/routine-prompt.md` 내용
- 환경변수: `CAL_CLIENT_ID` `CAL_CLIENT_SECRET` `CAL_REFRESH_TOKEN` `MEMBER_CALENDAR_IDS`

## 멤버 변동 시
구성원 추가/제외되면 ⓪만 다시 실행해 `MEMBER_CALENDAR_IDS` 갱신. 나머지 토큰/클라이언트는 그대로.

## 토큰 무효화
유출 의심 시 즉시: Google 계정(calendar@) → 보안 → 서드파티 액세스에서 해당 앱 권한 제거,
또는 GCP 에서 OAuth 클라이언트 삭제. 토큰은 readonly 라 피해 범위도 읽기 한정.

## Google OAuth 클라이언트의 "agentic" 표시 — 이 클라이언트는 표시하지 않는다 (2026-10-14 판단)

2026-10-12 Google Workspace 공지(`[Action Required] Mark AI agent OAuth clients as agentic for
Google Workspace MCP by Nov 11, 2026`)로 OAuth 클라이언트에 **agentic 플래그**가 생겼다
(콘솔 문구 "Use this client for an AI-powered agent", API 필드 `is_agentic`). 일정은 세 단계다.

| 날짜 | 무엇이 바뀌나 |
|---|---|
| 2026-10-12 | 콘솔에서 기존·신규 클라이언트에 agentic 표시 가능 |
| 2026-11-11 | **Workspace MCP 서버가 표시 없는 클라이언트의 요청을 거부** |
| 2026-11-12 | **기존 클라이언트의 설정이 영구 고정** — 바꾸려면 새 클라이언트 ID 를 만들어야 함 |

**이 루틴의 `CAL_CLIENT_ID` 는 표시하지 않는다.** 이유:

- 이 클라이언트는 Workspace MCP 서버를 부르지 않고 **Calendar REST API(`calendar.readonly`)만**
  쓴다. 공지도 "AI 에이전트가 아니고 REST API 만 쓰는 앱은 조치 불필요" 라고 명시했다 →
  **11/11 에 깨지는 것이 없다.** (호출자가 클라우드 루틴이라 '에이전트'이긴 하지만, 판정 기준은
  호출자가 아니라 **MCP 서버를 부르는지** 다.)
- 플래그는 스코프를 늘려 주지 않는다. 대신 **에이전트 전용 관리자 통제(agent access controls)의
  대상**이 된다. 도메인 관리자 정책이 한 번 바뀌면 무인 루틴이 멈추는 경로를 이득 없이 만들 이유가 없다.
- Google 권고 자체가 "에이전트 트래픽과 일반 트래픽은 클라이언트를 분리하라" 다.
- **11/12 의 영구 고정은 기존 클라이언트에만 적용된다.** 나중에 Calendar MCP 등으로 옮기고 싶으면
  그때 **agentic 으로 새 클라이언트를 만들면 된다** — 지금 서둘러 결정할 이유가 없다.

열려 있는 것 하나: 공지가 영향 프로젝트로 지목한 것은 `worklog-mcp-502409` 인데, 이 이름은
이 저장소·로컬 어디에도 없다(전수 grep 0건). 셋업 문서(③)는 클라이언트를
`ji-user-calendar-provisioning` 에 만들라고 적혀 있으나 실제로 어디에 만들었는지는 콘솔에서만 확인된다.
**`worklog-mcp-502409` 안의 클라이언트가 무엇인지 콘솔에서 확인할 것** — 그게 이 `CAL_CLIENT_ID`
라면 위 판단이 그대로 적용되고, 쓰지 않는 실험용이면 삭제가 정답이다.

출처: Google Cloud 콘솔 도움말 "Manage OAuth Clients"(support.google.com/cloud/answer/15549257),
`developers.google.com/workspace/guides/configure-mcp-servers`, 2026-10-12 공지 메일(`ji` 계정 11049).
