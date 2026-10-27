# 아직 구현하지 않은 워크플로·소스 (플러그인 스킬에서 분리)

플러그인 `SKILL.md`의 호출당 분량을 줄이면서(2026-10-27) 동작이 아닌 예정 항목을 여기로 옮겼다.
구현하게 되면 `plugin/skills/calendar-worklog/references/`의 해당 워크플로 파일로 되돌린다.

## 워크플로 4: monday 링크 보강 *(예정)*

캘린더 이벤트의 description에 monday item URL이 있으면:
- monday에서 해당 item의 현재 상태/담당자/실행 타임라인·실행 업무시간 산정 상태 조회
- description을 보강하여 업데이트
- 이미 외부 앱이 캘린더의 monday URL을 기준으로 monday 실행 타임라인과 실행 업무시간을 산정하므로, 본 워크플로는 보강·검증만 수행하고 별도 동기화나 중복 산정은 하지 않음

캘린더 업무 블록과 monday item은 겹칠 수 있습니다. 다만 description에 monday URL이 없는
일반 업무는 monday에 없는 업무일 수 있으므로, monday item 생성을 강제하거나 monday 시간으로
산정하지 않습니다.

(Phase 2에서 구체화)

## 워크플로 2 단계 C의 향후 확장 소스

5. *(향후 확장)* **SMS/iMessage**: macOS `~/Library/Messages/chat.db` SQLite로 가능하나
   Full Disk Access 권한 + 개인 메시지 다수라 우선순위 낮음. 회사 모바일 채널이 카카오톡/
   Slack이면 굳이 추가할 필요 없음.
