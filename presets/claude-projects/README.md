# Claude Projects 셋업

Claude 사용자가 calendar-worklog를 Claude Projects 위에서 돌리는 방법입니다.

## 사전 조건

- Claude 플랜: Pro / Max / Team / Enterprise (Free는 Projects 사용 불가)
- 회사가 Google Workspace를 쓰고 있어야 Google Calendar Connector가 의미 있음
- monday.com을 쓰는 경우, 회사 어드민이 다음을 해둬야 함:
  - monday.com → Admin → Permissions → AI Connectors → "Public Hosted MCP" 토글 ON

## 5단계 셋업

### 1단계: `user-config.yaml` — 마법사에게 맡기세요

**캘린더 ID를 직접 찾지 마세요.** 2~4단계(Project 생성 → prompt.md 업로드 → Connectors 연결)를
먼저 하고, Project 안에서 `셋업`이라고 치면 **워크플로 0(셋업 마법사)** 이 Connectors로
캘린더 4종·Slack ID·monday 보드를 조회해 완성된 YAML을 출력합니다.
그걸 `user-config.yaml`로 저장해 Project Knowledge에 추가하면 됩니다.

즉 이 문서의 실제 순서는 **2 → 3 → 4 → `셋업` → 1(업로드) → 5** 입니다.

다른 트랙에서 만든 `user-config.yaml`이 있으면 그대로 올리고 마법사를 건너뜁니다.

직접 작성하려면 `core/user-config.example.yaml`을 복사해 채웁니다
(이름·slack user_id·timezone·work_hours, 캘린더 ID 4개는 Google Calendar 웹 →
설정 → 해당 캘린더 → "캘린더 통합", monday 보드 ID는 선택).

### 2단계: Claude Project 생성
1. claude.ai → 좌측 메뉴 → Projects → **New Project**
2. 이름: 예) `📅 업무기록 도우미`
3. 설명: 자유

### 3단계: Project Knowledge 업로드
Project에 다음 파일을 업로드:
- `core/prompt.md`
- `core/user-config.example.yaml` (설정 형식 견본 — 셋업 마법사가 이 구조를 따름)
- `셋업`으로 만든 본인 `user-config.yaml` (마법사를 돌린 뒤)

> Custom instructions 칸에 prompt.md 내용을 직접 붙여넣어도 됩니다.
> 둘 다 가능하지만 Knowledge 업로드 방식이 길이 제한에서 자유로움.

### 4단계: Connectors 활성화
Claude.ai 우측 상단 또는 채팅 입력창의 도구 아이콘 → **Connectors**:

| Connector | 용도 | 필수 여부 |
|---|---|---|
| Google Calendar | 이벤트 읽기/쓰기 | 필수 |
| Slack | 메시지 검색 | 강력 권장 |
| monday.com | 보드 활동 / Time Tracking | 회사에서 monday 쓰면 필수 |

각 Connector 클릭 → OAuth 인증 진행.

### 5단계: 동작 확인
Project 안에서 새 채팅 시작 후:

```
지참 0835
```

→ 근태 캘린더에 08:30~08:35 이벤트가 생성되면 성공.

```
어제 일정 정리해줘
```

→ 어제 활동을 종합한 **등록 계획 표**가 먼저 출력됩니다. 표를 확인하고
`이대로 등록` 등으로 승인하면 새 이벤트들이 생성되면 성공.
(공용 캘린더 보호를 위해 확인 없이 바로 만들지 않습니다.)

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| Connector가 목록에 안 보임 | Claude 플랜 확인 (Pro 이상) / Connector Directory 새로고침 |
| monday.com 권한 오류 | 회사 어드민이 AI Connectors 토글 OFF한 상태 |
| 캘린더 잘못된 캘린더에 이벤트 생성됨 | user-config.yaml의 캘린더 ID 4개를 다시 확인 |
| Slack 메시지 검색이 비어 있음 | Slack workspace 권한 / DM 검색 권한 / 본인 slack_user_id 오타 |
| 색상이 노란색으로 들어감 | prompt.md에 `colorId 지정 안 함` 명시되어 있는지 확인. AI가 무시했으면 "색상 빼고 다시" 한마디 |
| AI가 "그 능력 없습니다" 응답 | 새 채팅으로 전환 / Connector 재인증 |

## 동작 검증 체크리스트

Phase 1 완료 기준입니다. 다음이 모두 되면 본인 셋업 OK:

- [ ] `지참 HHMM` 명령으로 근태 캘린더에 0830~HHMM 이벤트가 생긴다
- [ ] `어제 일정 정리해줘` 명령으로 Slack 활동이 시간순으로 식별된다
- [ ] 식별된 활동이 4개 캘린더 중 올바른 것에 배정된다
- [ ] 기존 일정과 중복되지 않는다 (회의 시간대를 덮어쓰지 않음)
- [ ] colorId 기본값이 유지된다 (회사 색상 그대로)
- [ ] description에 출처(Slack 시각, monday 보드 등)가 bullet으로 들어간다

## 한계 / 알려진 이슈

- **과거 AI 대화 검색**은 Claude 자체 기능이라 ChatGPT 트랙에는 없음. Claude 트랙의 우위.
- **Slack 검색 결과 개수**: Connector 정책에 따라 한 번에 20개 정도가 한계. 활동량이 많은 날은 여러 번 분할 검색됨.
- **monday Time Tracking 자동 동기화**는 Phase 2 예정. 현재는 monday URL을 description에 박는 것까지만.
