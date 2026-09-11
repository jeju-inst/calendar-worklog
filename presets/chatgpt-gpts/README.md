# ChatGPT 셋업 (Apps / Connectors 중심)

ChatGPT에서 calendar-worklog를 돌리는 방법입니다.

> **표준 경로는 Custom GPT보다 ChatGPT Project + Apps 연결입니다.**
> 연구원 다수는 채팅창만 쓰는 라이트 유저이므로, 먼저 Settings → Apps에서 Google Calendar,
> Gmail/Outlook, Slack, monday.com 같은 공식 Apps를 연결하는 경로를 검증합니다.
> Custom MCP / Developer Mode는 조직 관리자 또는 개발자가 별도 배포할 때 쓰는 고급 경로로 봅니다.

## 사전 조건 (플랜 요건 — 2026-05-29 확정: **Plus+ 필요**)

ChatGPT에는 크게 두 경로가 있습니다.

| 메커니즘 | 무료 플랜 | 비고 |
|---|---|---|
| **공식 Apps** (Google Calendar, Gmail/Outlook, Slack, monday.com 등) | ❌ **불가 (확정)** | 무료엔 **Google Calendar 커넥터 자체가 없음**(설정→앱·앱 디렉터리 모두 부재). Plus+부터 Google Calendar/Slack/monday 연결 가능 |
| **Custom MCP / Developer Mode** | 무료 주 경로 아님 | full MCP 및 write action 배포는 Business/Enterprise/Edu 중심. Pro는 read/fetch MCP 가능성이 있으나 write까지는 제한적 |

> **확정(2026-05-29 A/B 테스트):** 동일 기계에서 무료 vs Plus 계정을 비교한 결과, 무료엔
> Google Calendar 커넥터가 없어 캘린더 쓰기가 불가능 → **worklog 핵심 기능을 무료로는 못 돌린다.**
> 개인은 Plus 이상, 조직 배포는 Business/Enterprise/Edu의 Apps 관리·Action control을 검토.

- monday를 쓰는 경우, 회사 어드민이 AI/MCP 커넥터 접근을 허용해 둬야 함
  (monday Admin → Permissions → AI Connectors 또는 ChatGPT workspace Apps 설정)

### 무료 플랜 샌드박스 테스트 (2026-05-29 완료 — 결과: 무료 불가)

> **결과:** 무료 계정은 첫 항목(Google Calendar 커넥터 존재)에서 탈락. 아래 체크리스트는
> Plus/Business 검증이나 향후 재확인 시 절차로 참고.

**권장 격리 방식**: 임시 회사 Google 계정 하나 생성(어드민이면 쉬움) → 그 계정으로
무료 ChatGPT 로그인 + 자체 테스트 캘린더 사용. 계정·데이터가 한 번에 격리되어
production(공개) 캘린더를 오염시키지 않음. Docker 불필요. 단 임시 계정은 Slack/캘린더
히스토리가 없어 *배선 검증*용임. 활동 클러스터링 *내용*까지 임시 계정으로 검증하려면,
**테스트 Slack 채널**에 임시 계정으로 메시지 몇 개를 시각 간격을 두고 남긴 뒤 그 날짜로
`정리`를 돌린다. (worklog는 `from:<본인 user_id>`로 검색하므로 테스트 메시지의 작성자가
임시 계정이어야 잡힘. 쓰기 대상은 테스트 캘린더로.)

무료 GPT 계정 하나로 다음을 순서대로 확인:

- [x] `Settings → Apps`에 **Google Calendar / Slack / monday.com**이 보이는가 → **무료: ❌ 없음** (Plus: ✅)
- [ ] 각 App의 **Connect 버튼**이 활성화되는가 → 무료는 위에서 이미 탈락
- [ ] Slack **읽기**(메시지 검색)가 되는가
- [ ] Google Calendar **읽기**(일정 조회)가 되는가
- [ ] Google Calendar **쓰기**(이벤트 생성)가 되는가  ← 핵심. 읽기만 되고 쓰기는 막힐 수 있음
- [ ] monday를 **공식 App 또는 조직이 허용한 custom App/MCP**로 연결할 수 있는가
- [ ] 위가 되면 `지참 0835` / `어제 정리`까지 end-to-end 동작하는가

**확정 결과(2026-05-29)**: 무료 플랜 = **불가**. feature-matrix·메인 README의 ChatGPT 플랜
요건을 Plus+로 갱신 완료.

## 1단계: `user-config.yaml` 준비

**손으로 채우지 마세요.** 3단계까지 마친 뒤 채팅에 `셋업`이라고 치면,
`prompt.md`의 **워크플로 0(셋업 마법사)** 이 커넥터로 캘린더 4종·Slack ID·monday 보드를
직접 조회해 완성된 YAML을 출력해 줍니다. 그걸 `user-config.yaml`로 저장해
Project 파일에 올리면 끝입니다. 캘린더 ID를 찾아다닐 일이 없습니다.

즉 순서는 **2단계(Apps 연결) → 3단계(프롬프트 탑재) → `셋업` → YAML 업로드** 입니다.

이미 Claude·Codex 트랙에서 만든 `user-config.yaml`이 있으면 **그 파일을 그대로 재사용**하고
마법사를 건너뜁니다. 트랙이 달라도 설정은 단일 소스입니다.

직접 작성하고 싶으면 `core/user-config.example.yaml`을 복사해 채워도 됩니다(캘린더 ID 4개 /
slack_user_id / monday 보드 ID / work_hours).

## 2단계: 데이터 소스 Apps 연결

`Settings → Apps`에서:

| 소스 | 연결 방법 | 비고 |
|---|---|---|
| Google Calendar | 공식 커넥터 → Connect (OAuth) | 이벤트 읽기/쓰기. 필수 |
| Slack | 공식 커넥터 → Connect (OAuth) | 메시지 검색. 강력 권장 |
| monday.com | 공식 App이 있으면 Connect / 없으면 조직 관리자 검토 후 custom App/MCP | 회사에서 monday 쓰면 필수 |

> 쓰기/수정 작업 시 ChatGPT가 실행 전 **확인 모달**을 띄울 수 있습니다. 이건 prompt.md의
> "등록 계획 표 확인 게이트"와 별개의 2차 안전장치입니다.

### Custom MCP / Developer Mode가 필요한 경우

공식 Apps만으로 monday 조회나 Calendar write가 부족하면 조직 관리자/개발자 트랙에서 custom MCP를 검토합니다.
이 경로는 라이트 유저가 직접 설정하는 기본 경로가 아니라, Business/Enterprise/Edu workspace에서
관리자가 검증·게시하는 방식이 적합합니다.

## 3단계: 프롬프트 + 설정 탑재

**권장: ChatGPT Project** (Instructions + 파일 + 커넥터를 함께 묶음)
1. 새 Project 생성 (예: `업무기록 도우미`)
2. Project **Instructions** 칸에 `presets/chatgpt-gpts/instructions.md` 내용 붙여넣기
3. Project 파일에 `core/prompt.md` + 본인 `user-config.yaml` 업로드

또는 **Custom GPT** (공유·패키징용):
- Instructions 칸에 `instructions.md` 붙여넣기, Knowledge에 `prompt.md` + `user-config.yaml` 업로드
- 단, Custom GPT는 MCP 커넥터 직접 호출이 표준이 아니므로 도구 호출은 위 계정 커넥터에 의존

## 4단계: 동작 확인

```
지참 0835
```
→ 근태 캘린더에 08:30~08:35 이벤트 생성 (쓰기 확인 모달 승인)

```
어제 정리
```
→ 어제 활동 종합 → **등록 계획 표** 출력 → 승인하면 빈 슬롯에 업무 블록 생성

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| App Connect 버튼이 비활성 | 플랜/지역/workspace 설정 제한 가능 → 무료/Plus/Business 각각 확인 |
| Slack이 안 보이거나 연결 안 됨 | 공식 Slack app은 paid ChatGPT plan 필요. workspace admin 제한도 확인 |
| monday 권한 오류 | 회사 어드민이 AI 커넥터 또는 ChatGPT app 접근 비허용 |
| 도구를 안 부르고 글로만 답함 | 커넥터 연결/인증 재확인, 새 대화로 전환 |
| 색상이 노란색 등으로 들어감 | prompt.md의 colorId 미지정 규칙 무시됨 → "색상 빼고 다시" |

## Claude 트랙과의 차이

- **과거 AI 대화 검색**은 Claude 고유 기능. ChatGPT 트랙엔 없음 → 활동 소스가 Slack/monday/캘린더로 한정
- 나머지(캘린더·Slack·monday)는 동일하게 동작

## 참고

- [Developer mode and MCP apps in ChatGPT — OpenAI Help](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt-beta)
- 설정 경로 등 UI는 변동될 수 있으니 위 공식 문서를 우선 확인
