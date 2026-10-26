# 내가(=namun) 체크할 것 — 주간보고 무인화 라이브까지

> 콘솔 로그인·PII가 필요해 어시스턴트가 대신 못 하는 단계만. 순서대로.
> 상세 화면설명은 `README.md` ③④⑥ 참조.

## ☐ 1. OAuth 클라이언트 ID 생성 (GCP 콘솔)
- 프로젝트: **`ji-user-calendar-provisioning`**
- 동의화면: User type **Internal**, 앱 게시
- 사용자 인증 정보 → OAuth 클라이언트 ID → 유형 **데스크톱 앱**
- ⚠️ JSON 다운로드는 조직정책에 막혀 있음 → **화면에 뜨는 `client_id` / `client_secret` 두 문자열만 복사**
  (어시스턴트가 `get_refresh_token.py`를 파일 대신 이 두 값을 env로 받게 고쳐둠)

## ☐ 2. refresh token 발급 (로컬, 1회)
```
CAL_CLIENT_ID=<복사한 id> CAL_CLIENT_SECRET=<복사한 secret> \
  ~/dev/ji-calendar-provision/.venv/bin/python automation/get_refresh_token.py
```
- 브라우저 열리면 **반드시 `calendar@ji.re.kr` 로 로그인** + 읽기 허용
- 출력된 `CAL_CLIENT_ID` / `CAL_CLIENT_SECRET` / `CAL_REFRESH_TOKEN` 보관

## ☐ 3. (선택) 캘린더 ID 목록 재산출 — 멤버 변동 있었으면만
- 현재 `scratch/calendar_ids_env.json` = 88개, hub_readable=88 검증됨. 변동 없으면 **건너뜀**.
- 변동 시 README ⓪ 실행 → `MEMBER_CALENDAR_IDS` 값 갱신

## ☐ 4. /schedule 루틴 등록 (Claude Code)
- 일정: **매주 금 18:00 (반복)**
- 저장소: 이 repo (`calendar-worklog`)
- 커넥터: **Slack + monday 만 체크** (Google Calendar 커넥터 불필요)
- 프롬프트: `automation/routine-prompt.md` 내용 붙여넣기
- 환경변수 5개:
  - `CAL_CLIENT_ID`
  - `CAL_CLIENT_SECRET`
  - `CAL_REFRESH_TOKEN`
  - `MEMBER_CALENDAR_IDS` (= `scratch/calendar_ids_env.json` 내용)
  - `ALERT_DM_UID` (실패 알림 DM 을 받을 Slack UID)

---
## 어시스턴트가 먼저 끝내줄 것 (네 승인 대기)
- [ ] `get_refresh_token.py` 를 env(`CAL_CLIENT_ID`/`CAL_CLIENT_SECRET`) 입력 방식으로 수정
- [ ] `automation/` 커밋 (루틴이 GitHub에서 clone 하므로 필수 / PII 없음·코드와 문서뿐)
