# calendar-worklog

협업툴(Slack / monday.com / AI 세션 등)에 흩어진 활동 흔적을 모아
캘린더에 시간 단위 업무일지로 기록해 주는 프롬프트 키트.

> **현재 상태: Phase 1 (WIP)**
> 제주연구원(JI) 내부 워크플로에 맞춰 구체화하는 단계입니다.
> 다른 회사/조직에서 그대로 쓰기엔 회사 고유 규칙(4개 캘린더 분류, 근태 규칙 등)이
> 녹아 있어요. Phase 3에서 일반화 예정.

---

## 무엇을 하는가

채팅 한 줄로 다음이 됩니다:

- **"지참 0835"** → 근태 캘린더에 `08:30~08:35 지참 08:35` 자동 등록
- **"어제 일정 정리해줘"** → Slack / AI 세션 / monday 활동을 종합해 어제 빈 캘린더 슬롯에 업무 블록을 1시간 단위로 채움. 캘린더 4종(과제/업무/근태/기타)에 자동 배정
- **"이번 주 정리해줘"** *(예정)* → 주간 단위 사후 기록
- **"이번 달 직원소통공감회의 자료 정리해줘"** → 매월 과제별 주요 추진사항·특이사항을 monday / Slack / Calendar / 과제 폴더에서 종합해 공유 회의자료 Doc의 본인 섹션 초안 작성. 상세: [docs/monthly-meeting-report.md](./docs/monthly-meeting-report.md)

작동 원리는 사용자별 설정(`user-config.yaml`)과 공통 프롬프트(`core/prompt.md`)를
AI에 함께 주입하는 방식. AI는 Claude / ChatGPT 어느 쪽이든 OK입니다.

## 듀얼 메인 (Claude / ChatGPT)

monday MCP가 양쪽 다 정식 지원되어 기능 격차는 거의 없습니다.

| 트랙 | 셋업 비용 | 회사 내 사용자 분포 |
|---|---|---|
| Claude Projects | 5분 (Connector 토글) | 소수 |
| ChatGPT (Plus/Pro + Developer Mode MCP) | 10분 (1회 MCP URL 등록) | 다수 |
| Codex / Claude Code / Cursor | 10분 (mcp.json 편집) | 코드 사용자 |
| Gemini Gems | 보조 |  |

각 트랙별 셋업은 `presets/` 디렉토리 참조. 어느 트랙을 고를지는
[docs/decision-tree.md](./docs/decision-tree.md), 능력 비교는
[docs/feature-matrix.md](./docs/feature-matrix.md) 참조.

## 구조

```
calendar-worklog/
├── README.md                      # 지금 이 문서
├── core/
│   ├── prompt.md                  # AI에 주입할 본체 (사용자/AI 무관)
│   └── user-config.example.yaml   # 사용자 설정 템플릿
├── presets/
│   ├── claude-projects/           # Claude Projects 셋업 가이드
│   ├── chatgpt-gpts/              # ChatGPT (Developer Mode + MCP) 셋업 가이드
│   ├── codex/                     # Codex CLI (config.toml + AGENTS.md) 셋업 가이드
│   └── claude-code/               # Claude Code (CLAUDE.md + MCP) 셋업 가이드
├── docs/
│   ├── onboarding.md              # 동료 사용자용 1페이지 인트로
│   ├── setup.md                   # 트랙별 셋업 가이드 (A/B/C/D 통합)
│   ├── seminar-intro.md           # 부서 세미나용 발표 자료
│   ├── feature-matrix.md          # 트랙별 기능 비교표
│   ├── decision-tree.md           # "나는 어느 트랙으로?" 1페이지 가이드
│   ├── openai-solution-review.md  # OpenAI 기반 가능 작업/플랜 검토
│   └── openai-test-scenarios.md   # 무료/Plus 검토 기능 시나리오
└── examples/                      # (예정)
```

> **유지보수 주의 — 프롬프트 본체가 두 벌입니다.**
> `core/prompt.md`(에이전트 중립. ChatGPT·Claude Projects·Codex가 읽음)와
> `plugin/skills/calendar-worklog/SKILL.md`(Claude Code 플러그인용)는 **같은 워크플로의
> 평행 사본**입니다. 플러그인은 자기 디렉터리 밖 파일을 싣지 못해 include가 불가능합니다.
> 한쪽 워크플로를 고치면 다른 쪽도 함께 고치세요.

## 빠르게 시작 (Claude Projects)

1. claude.ai → Projects → New Project
2. Project knowledge에 `core/prompt.md` 업로드
3. Connectors에서 Google Calendar / Slack / monday.com 켜기
4. 채팅에 `셋업` 입력 → **셋업 마법사**가 캘린더 4종·Slack ID·monday 보드를 직접 조회해
   완성된 `user-config.yaml`을 출력 → 그 파일을 Project knowledge에 추가
5. `"지참 0835"` 또는 `"어제 일정 정리해줘"` 입력

캘린더 ID를 손으로 찾아 적을 필요가 없습니다. 마법사는 Claude Code 플러그인뿐 아니라
**모든 트랙에서 동작**합니다(파일을 못 쓰는 채팅 환경에서는 YAML을 출력해 줍니다).

자세한 단계는 [presets/claude-projects/README.md](./presets/claude-projects/README.md).

## 로드맵

| Phase | 상태 | 내용 |
|---|---|---|
| 1 | 진행 중 | JI 전용으로 본인 워크플로 동작시키기 |
| 2 | 예정 | 사내 동료 3~5명이 매일 쓰는 수준으로 안정화 |
| 3 | 예정 | 회사 고유 규칙을 config로 분리, 코어 추상화 |
| 4 | 예정 | 영문 README 추가 + 퍼블릭 공개 |

## 라이선스

(Phase 4에서 결정)
