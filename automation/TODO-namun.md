# 내가(=namun) 체크할 것 — 주간보고 무인화

> 콘솔 로그인·PII가 필요해 어시스턴트가 대신 못 하는 단계만.
> 상세 화면설명은 `README.md` ③④⑥ 참조.

## 지금 남은 것

### ☐ A. OAuth 클라이언트에 "agentic" 표시 — **11/11 마감**
- 콘솔: `https://console.cloud.google.com/apis/credentials?project=ji-user-calendar-provisioning&authuser=1`
- 데스크톱 앱 클라이언트를 열어 **"AI 기반 에이전트에 이 클라이언트 사용"** 체크.
  어느 클라이언트인지는 루틴 env `CAL_CLIENT_ID` 앞 숫자로 대조.
- 체크박스 한 번이면 끝 — **스코프는 늘지 않고 토큰 재발급도 필요 없다.**
- **11/12 이후에는 설정이 영구 고정**돼, 바로잡으려면 클라이언트를 새로 만들고
  refresh token 까지 재발급(④)해야 한다. 그래서 마감이 실질적이다.
- 들어간 길에 공지가 지목한 다른 프로젝트(`worklog-mcp-502409`)의 클라이언트도 확인.
  쓰지 않는 실험용이면 삭제가 정답. 배경은 `README.md` 의 agentic 절.

### ☐ B. `/schedule` 루틴 프롬프트 재붙여넣기
- 클라우드 루틴은 **등록 당시 붙여넣은 텍스트로 돈다.** 저장소를 고쳐도 프롬프트는 안 바뀐다.
  (`read_calendars.py` 같은 코드는 fresh clone 이라 머지만으로 적용된다.)
- 현재 등록본은 2026-07-17 판이라 그 뒤 반영분이 빠져 있다 — 명부 대조 단계,
  실패 알림 단계(단계 6) 둘 다.
- 할 일: `automation/routine-prompt.local.md` 전체를 루틴 프롬프트에 다시 붙여넣고,
  env 에 **`ALERT_DM_UID`**(실패 알림 DM 받을 Slack UID) 를 추가.

### ☐ C. 재붙여넣기 후 첫 금요일 게시 확인
- A·B 를 하고 나서 첫 금요일에 #연구부서장 에 **실별 1건씩 총 2건**이 올라왔는지 본다.
- B 가 끝난 뒤에는 실패 시 DM 이 오므로, 그 다음부터는 눈으로 볼 필요가 없다.
  **B 전까지는 조용한 실패가 보이지 않는다** — 그래서 이 확인이 B 와 묶여 있다.

---

## 이미 끝난 셋업 (기록용)

- ☑ 1. OAuth 클라이언트 ID 생성 (`ji-user-calendar-provisioning`, 데스크톱 앱, 동의화면 Internal)
  - JSON 다운로드는 조직정책에 막혀 있어 `client_id`/`client_secret` 문자열만 복사했다.
    `get_refresh_token.py` 가 파일 대신 이 두 값을 env 로 받는 이유.
- ☑ 2. refresh token 발급 (`calendar@ji.re.kr` 로그인, readonly 허용)
- ☑ 4. `/schedule` 루틴 등록 — 매주 금 18:00, 커넥터는 **Slack + monday 만**
  (Google Calendar 커넥터 불필요), 당시 넣은 env 4개:
  `CAL_CLIENT_ID` `CAL_CLIENT_SECRET` `CAL_REFRESH_TOKEN` `MEMBER_CALENDAR_IDS`
  - **`ALERT_DM_UID` 는 아직 없다** — 위 B 에서 프롬프트를 재붙여넣을 때 함께 추가한다.

## 멤버 변동이 있었을 때만
- 현재 `scratch/calendar_ids_env.json` = 88개, hub_readable=88 검증됨. 변동 없으면 건너뜀.
- 변동 시 `README.md` ⓪ 실행 → 루틴 env `MEMBER_CALENDAR_IDS` 값 갱신.
