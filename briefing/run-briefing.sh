#!/bin/bash
# 아침 브리핑 러너 — launchd(매 평일 08:30)가 호출한다.
#
# launchd는 최소 환경(PATH 거의 없음, 로그인 셸 미경유)으로 띄우므로 여기서 전부 세운다.
# 실측(2026-07-20, env -i 상태): monday·Slack·캘린더·mailskill·messages 5소스 모두 가용.
set -uo pipefail

REPO="$HOME/dev/calendar-worklog"
LOGDIR="$REPO/briefing/logs"
LOG="$LOGDIR/$(date +%Y-%m-%d).log"
TIMEOUT=900          # 15분. 넘으면 죽이고 실패로 본다.
SLACK_SELF="U09M60HKY73"

# launchd 최소 env 보정. mailskill(/opt/homebrew/bin)·claude(~/.local/bin) 둘 다 필요.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="${HOME:-/Users/namun}"
export LANG="en_US.UTF-8"

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T %Z') 브리핑 시작 ==="

cd "$REPO" || { echo "FATAL: repo 없음 $REPO"; exit 1; }

for f in briefing/prompt.md core/prompt.md core/user-config.yaml; do
  [ -r "$f" ] || { echo "FATAL: 읽을 수 없음 $f"; exit 1; }
done

# 프롬프트 조립: 브리핑 워크플로 + 사용자 설정(캘린더 ID 등)을 한 번에 먹인다.
# core/prompt.md 전체는 넣지 않는다 — 사후 기록 워크플로라 브리핑엔 불필요하고,
# 캘린더 쓰기 지침이 섞이면 "읽기 전용" 계약이 흐려진다.
PROMPT=$(cat <<EOF
$(cat briefing/prompt.md)

---

# user-config.yaml (본인 설정 — 캘린더 ID·근무시간·monday 보드 등)

\`\`\`yaml
$(cat core/user-config.yaml)
\`\`\`

---

# 실행 지시

지금 이 실행은 위 문서의 **무인 실행**이다. 사람이 보지 않는다.
- 오늘 날짜: $(date '+%Y-%m-%d (%a)') KST
- 단계 A~F를 끝까지 수행하고, 완성된 브리핑을 Slack DM으로 **반드시 발송**한 뒤 종료한다.
- 발송 대상: 본인 DM (Slack user \`$SLACK_SELF\`).
- 캘린더는 위 config의 \`calendars\` 4개 + \`read_only_calendars\`를 **ID로 지정해** 조회한다.
  primary 캘린더만 보면 안 된다(비어 있다).
- 질문하지 말고, 확인 게이트 없이 진행한다. 애매하면 브리핑 본문에 "확인 필요"로 적는다.
- 읽기 전용 계약을 지킨다: 캘린더 생성/수정 금지, 메일 회신 금지, monday 수정 금지,
  메시지 답장 금지. 유일한 쓰기는 위 Slack DM 1건.
- 마지막에 표준출력으로 \`BRIEFING_SENT\` 또는 \`BRIEFING_FAILED: <사유>\` 한 줄을 남긴다.
EOF
)

ALLOWED='Bash(mailskill:*),Bash(gw:*),Bash(msg:*),Bash(date:*),mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Gmail__get_thread,mcp__claude_ai_monday_com__get_user_context,mcp__claude_ai_monday_com__get_board_items_page,mcp__claude_ai_monday_com__get_updates,mcp__claude_ai_monday_com__get_board_activity,mcp__claude_ai_monday_com__all_api_read,mcp__claude_ai_Google_Calendar__list_events,mcp__claude_ai_Google_Calendar__list_calendars,mcp__plugin_slack_slack__slack_search_public_and_private,mcp__plugin_slack_slack__slack_read_thread,mcp__plugin_slack_slack__slack_read_channel,mcp__plugin_slack_slack__slack_search_users,mcp__plugin_slack_slack__slack_send_message,mcp__messages__messages_threads,mcp__messages__messages_read,mcp__messages__messages_unread'

# perl alarm = macOS에 timeout(1)이 없어서 쓰는 대체
OUT=$(perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" \
      claude -p "$PROMPT" --allowedTools "$ALLOWED" </dev/null 2>&1)
RC=$?

echo "$OUT"
echo "--- claude rc=$RC ---"

if [ $RC -ne 0 ] || ! printf '%s' "$OUT" | /usr/bin/grep -q 'BRIEFING_SENT'; then
  echo "실패 감지 — 알림 발송 시도"
  # 조용히 죽지 않는다. 브리핑이 '안 온 것'과 '실패한 것'을 구분할 수 있어야 한다.
  /usr/bin/osascript -e 'display notification "아침 브리핑 생성 실패 — 로그 확인" with title "calendar-worklog"' 2>/dev/null
  echo "=== $(date '+%F %T') 브리핑 실패 (rc=$RC) ==="
  exit 1
fi

echo "=== $(date '+%F %T') 브리핑 완료 ==="

# 로그는 30일치만 유지
/usr/bin/find "$LOGDIR" -name '*.log' -mtime +30 -delete 2>/dev/null
exit 0
