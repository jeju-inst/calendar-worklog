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
- 환경변수: `CAL_CLIENT_ID` `CAL_CLIENT_SECRET` `CAL_REFRESH_TOKEN` `MEMBER_CALENDAR_IDS` `ALERT_DM_UID`(실패 알림을 받을 Slack UID)

## 멤버 변동 시
구성원 추가/제외되면 ⓪만 다시 실행해 `MEMBER_CALENDAR_IDS` 갱신. 나머지 토큰/클라이언트는 그대로.

## 토큰 무효화
유출 의심 시 즉시: Google 계정(calendar@) → 보안 → 서드파티 액세스에서 해당 앱 권한 제거,
또는 GCP 에서 OAuth 클라이언트 삭제. 토큰은 readonly 라 피해 범위도 읽기 한정.

## Google OAuth 클라이언트의 "agentic" 표시 — 11/11 전에 표시한다 (2026-10-14 판단)

2026-10-12 Google Workspace 공지(`[Action Required] Mark AI agent OAuth clients as agentic for
Google Workspace MCP by Nov 11, 2026`)로 OAuth 클라이언트에 **agentic 플래그**가 생겼다
(콘솔 문구 "Use this client for an AI-powered agent", API 필드 `is_agentic`). 일정은 세 단계다.

| 날짜 | 무엇이 바뀌나 |
|---|---|
| 2026-10-12 | 콘솔에서 기존·신규 클라이언트에 agentic 표시 가능 |
| 2026-11-11 | **Workspace MCP 서버가 표시 없는 클라이언트의 요청을 거부** |
| 2026-11-12 | **기존 클라이언트의 설정이 영구 고정** — 바꾸려면 새 클라이언트 ID 를 만들어야 함 |

**이 루틴의 `CAL_CLIENT_ID` 를 11/11 전에 agentic 으로 표시한다.** 단 두 가지를 구분해야 한다.

- **거부(11/11)는 당장 해당 없다.** 이 클라이언트는 Workspace MCP 서버를 부르지 않고 Calendar
  REST API(`calendar.readonly`)만 쓰므로, 표시하지 않아도 **11/11 에 깨지는 것은 없다.**
- **그러나 분류 기준은 "MCP 를 부르는가" 가 아니다.** 공지는 "AI 에이전트에 속한 OAuth 클라이언트를
  식별하라 — **현재 Workspace REST API 만 쓰는 에이전트도 포함**" 이라고 적었고, 콘솔 도움말도
  agentic 을 "에이전트, 자동 도구 실행, 그리고 MCP 통합" 으로 정의한다(MCP 는 그중 한 경우일 뿐).
  이 루틴은 **무인 AI 에이전트가 캘린더 컨텍스트를 읽어 보고를 생성·게시**하는 것이므로 정의상 agentic 이다.
  공지의 면제 문구("AI 에이전트가 아니고 REST 만 쓰는 앱")는 우리에게 적용되지 않는다.

표시하지 않을 때의 비용:

- 도메인 관리자가 에이전트 트래픽에 **의도된 통제를 적용할 수 없다.** 우리 도메인이 AI 거버넌스를
  세우는 중인데 우리 에이전트부터 사람 트래픽으로 위장하는 셈이 된다.
- **11/12 이후에는 바로잡을 길이 클라이언트 재발급뿐이다** — 새 클라이언트 생성 + `calendar@` 로
  refresh token 재발급(④) + 루틴 env 3개(`CAL_CLIENT_ID`/`CAL_CLIENT_SECRET`/`CAL_REFRESH_TOKEN`) 교체.

표시해도 **스코프는 늘지 않는다**(공지·도움말 모두 명시). 대신 에이전트 전용 관리자 통제의 대상이
되는데, 그것이 바로 의도된 동작이고 관리자 콘솔은 우리가 쥐고 있다.

그 위험을 감지할 장치는 **이 PR 에서 붙였다**(처음 이 절을 쓸 때는 없었다). 에이전트 정책이
캘린더 호출을 막으면 `read_calendars.py` 가 그 캘린더만 `error` 로 남기고(전부 막히면 exit 1),
루틴은 단계 6에서 `ALERT_DM_UID` 로 DM 을 보낸다 — 보고를 2건 중 1건만 올린 경우도 포함이다.

**단, 알림은 `/schedule` 에 프롬프트를 다시 붙여넣은 뒤부터 동작한다.** 코드(`read_calendars.py`)는
머지만으로 적용되지만 단계 6은 프롬프트에 있고, 클라우드 루틴은 등록 당시 붙여넣은 텍스트로 돈다.
재붙여넣기 전까지는 여전히 **금요일에 보고가 올라왔는지 눈으로 봐야 한다** — 표시 후 첫 금요일(11/13).

공지의 "에이전트용·비에이전트용 클라이언트를 분리하라" 권고에 따라 **전용 클라이언트를 새로 만드는
방법도 있으나**, 이 클라이언트는 애초에 이 무인 루틴만 쓰므로 분리할 비에이전트 트래픽이 없다 →
**기존 클라이언트에 표시하는 것으로 충분하다**(콘솔 체크박스 한 번, 토큰 재발급 불필요).

열려 있는 것 하나: 공지가 영향 프로젝트로 지목한 것은 `worklog-mcp-502409` 인데, 이 이름은
이 저장소·로컬 어디에도 없다(전수 grep 0건). 셋업 문서(③)는 클라이언트를
`ji-user-calendar-provisioning` 에 만들라고 적혀 있으나 실제로 어디에 만들었는지는 콘솔에서만 확인된다.
**표시하러 콘솔에 들어갈 때 `worklog-mcp-502409` 안의 클라이언트가 무엇인지 함께 확인할 것** —
그게 이 `CAL_CLIENT_ID` 라면 거기서 표시하면 되고, 쓰지 않는 실험용이면 삭제가 정답이다.

출처: Google Cloud 콘솔 도움말 "Manage OAuth Clients"(support.google.com/cloud/answer/15549257),
`developers.google.com/workspace/guides/configure-mcp-servers`, 2026-10-12 공지 메일(`ji` 계정 11049).
