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

### ☐ B. 루틴이 **등록돼 있지 않다** — 새로 등록
2026-10-30 실측. 그 전까지 이 문서는 "7월판 프롬프트로 돌고 있으니 다시 붙여넣기만 하면
된다" 고 적고 있었는데, 그 전제가 틀렸다.

- 개인 계정 루틴 목록(`/schedule` → list) **10건 중 주간 과제 보고는 없고, 10건 전부 disabled.**
- #연구부서장 게시 이력도 주 단위가 아니다 — 6/6 · 6/12 · 6/21 · 7/11 · 7/17 · 9/4 · 9/21
  일곱 번뿐이고 **9/21 이후로는 한 건도 없다**(9/25 · 10/2 · 10/9 · 10/16 · 10/23 전부 공백).
- 회사 계정(`claude-work`)에 등록돼 있을 가능성은 CLI 로 확인할 수 없다 —
  그 세션의 토큰은 inference-only 스코프라 routines API 가 401 을 돌려준다.
  https://claude.ai/code/routines 에서 **두 계정을 각각** 보면 확정된다.

할 일: `/schedule` 로 **새로 등록**한다.
- 프롬프트: `automation/routine-prompt.local.md` **전체**
- env 5개: `CAL_CLIENT_ID` `CAL_CLIENT_SECRET` `CAL_REFRESH_TOKEN` `MEMBER_CALENDAR_IDS`
  **`ALERT_DM_UID`**(실패 알림 DM 받을 Slack UID)
- 커넥터: Slack + monday / 일정: 매주 금 18:00 (KST)
- 저장소 코드(`read_calendars.py`)는 fresh clone 이라 최신이 자동으로 쓰인다.
  **프롬프트만은 등록 시점 텍스트로 고정**되므로, 프롬프트를 고칠 때마다 루틴을 다시 손봐야 한다.

### ☐ C. 등록 후 첫 금요일 게시 확인
- B 를 하고 나서 첫 금요일에 #연구부서장 에 **실별 1건씩 총 2건**이 올라왔는지 본다.
- 등록이 끝나면 실패 시 DM 이 오므로, 그 다음부터는 눈으로 볼 필요가 없다.
  **B 전까지는 조용한 실패가 보이지 않는다** — 9/21 이후 5주 공백이 아무에게도 안 보인 것이 그 증거다.

---

## 이미 끝난 셋업 (기록용)

- ☑ 1. OAuth 클라이언트 ID 생성 (`ji-user-calendar-provisioning`, 데스크톱 앱, 동의화면 Internal)
  - JSON 다운로드는 조직정책에 막혀 있어 `client_id`/`client_secret` 문자열만 복사했다.
    `get_refresh_token.py` 가 파일 대신 이 두 값을 env 로 받는 이유.
- ☑ 2. refresh token 발급 (`calendar@ji.re.kr` 로그인, readonly 허용)
- ☐ 4. `/schedule` 루틴 등록 — **끝난 것으로 적어뒀으나 2026-10-30 확인 결과 등록돼 있지 않다.**
  위 B 로 올렸다. (7월에 한 번 등록했더라도 지금 남아 있지 않다.)

## 멤버 변동이 있었을 때만
- 현재 `scratch/calendar_ids_env.json` = 88개, hub_readable=88 검증됨. 변동 없으면 건너뜀.
- 변동 시 `README.md` ⓪ 실행 → 루틴 env `MEMBER_CALENDAR_IDS` 값 갱신.
