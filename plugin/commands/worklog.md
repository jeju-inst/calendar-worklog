---
description: 캘린더 업무기록 — /worklog <setup|late|day|week|monthly|now>
argument-hint: <setup|late HHMM|day [날짜]|week [지난주|이번주]|monthly [이번달|지난달]|now <제목 날짜 시작-종료>>
---

`$ARGUMENTS`의 첫 토큰으로 분기한다. **calendar-worklog 스킬을 호출**해서 본문 규칙을 따른다.

## 디스패치

| 첫 토큰 | 동작 | 비고 |
|---|---|---|
| (없음) | 도움말 표시 | 아래 도움말 |
| `setup` | 셋업 마법사 | calendar-worklog 스킬의 "워크플로 0: 셋업 마법사" 수행 |
| `late` | 워크플로 1-A (지참) | `HHMM` 또는 `HH:MM` 필요. 계획 게이트 생략하고 바로 등록 |
| `leave` / `연가` / `휴가` / `공가` / `병가` | 워크플로 1-B (전일근태) | 날짜 + 유형. 게이트 생략 가능 |
| `day` | 워크플로 2 (일자 업무 기록) | 인자: `어제` / `오늘` / `5/30` / `2026-05-30` 등. 미지정 시 어제 |
| `week` | 워크플로 5 (주간 과제 보고) | 인자: `이번주` / `지난주` / 미지정 시 이번 주 |
| `monthly` | 워크플로 6 (월간 직원소통공감회의 자료) | 인자: `이번달` / `지난달` / 미지정 시 이번 달. 읽기·집계 전용, 초안만 제시 |
| `now` | 워크플로 3 (명시 등록) | 인자: 제목 + 날짜 + 시간 |

첫 토큰이 위 키워드가 아니면 사용자 발화 그대로 calendar-worklog 스킬에 넘긴다 (자연어 모드).

## 사전 점검 (모든 분기 공통, `setup` 제외)

1. `~/.config/calendar-worklog/user-config.yaml`을 Read.
2. 없으면 `/worklog setup`을 먼저 돌리라고 안내하고 중단.
3. 있으면 그 값을 본인 설정으로 간주하고 calendar-worklog 스킬 본문 따르기.

## 인자 없이 호출됐을 때 (도움말)

```
calendar-worklog — 사용 가능한 명령

/worklog setup            셋업 마법사 (최초 1회)
/worklog late 0835        지참 등록 (08:30~08:35)
/worklog day              어제 일정 정리
/worklog day 5/30         특정 일자 정리
/worklog week             이번 주 과제 보고
/worklog week 지난주       지난주 과제 보고
/worklog monthly          이번 달 직원소통공감회의 자료 초안
/worklog now <제목 날짜 시간>  단일 일정 즉시 등록

자연어 발화도 인식: "지참 0835", "어제 정리", "이번 주 보고", "이번 달 직원소통공감회의 자료 정리"
```
