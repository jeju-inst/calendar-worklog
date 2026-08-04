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

# 브리핑 전용 장기 토큰(claude setup-token 으로 발급)이 있으면 그걸로 인증한다.
# 이러면 사용자가 평소 쓰는 대화형 claude 로그인(OAuth 세션)이 만료돼도 브리핑은
# 자기 토큰으로 독립적으로 계속 돈다 — 2026-08-03 처럼 로그인 풀려 브리핑이 통째로
# 죽는 사고를 근본 예방한다. 토큰 파일이 없으면 기존 OAuth 세션으로 폴백(하위호환).
#   발급: `claude setup-token` → 출력 토큰을 아래 파일에 저장(chmod 600)
#   저장: ~/.config/calendar-worklog/claude-token
# 이 판정은 반드시 위 exec 리다이렉트 *뒤*에 있어야 한다 — 앞에 두면 어느 자격증명으로
# 돌았는지가 날짜별 로그에 안 남고 launchd stderr 로만 새서, 사후 추적이 불가능해진다.
CLAUDE_TOKEN_FILE="$HOME/.config/calendar-worklog/claude-token"
TOKEN_MODE=session   # session | dedicated — 실패 안내 문구를 가르는 값
if [ -r "$CLAUDE_TOKEN_FILE" ] && [ -s "$CLAUDE_TOKEN_FILE" ]; then
  export CLAUDE_CODE_OAUTH_TOKEN="$(cat "$CLAUDE_TOKEN_FILE")"
  TOKEN_MODE=dedicated
  echo "인증: 브리핑 전용 장기 토큰 사용(대화형 로그인과 독립)"
else
  echo "인증: 전용 토큰 없음 — 기존 OAuth 세션 사용(로그인 풀리면 같이 죽음). setup-token 권장."
fi

cd "$REPO" || { echo "FATAL: repo 없음 $REPO"; exit 1; }

for f in briefing/prompt.md core/prompt.md core/user-config.yaml; do
  [ -r "$f" ] || { echo "FATAL: 읽을 수 없음 $f"; exit 1; }
done

# 오늘 할 일 리스트 링크(담당자숨김 뷰). 레포엔 안 박고 런타임 설정에서 읽어 DM 말미에 붙인다.
LIST_URL=$(/usr/bin/python3 -c 'import json,os;print(json.load(open(os.path.expanduser("~/.config/calendar-worklog/todo-list.json"))).get("list_url",""))' 2>/dev/null || true)
LIST_LINE=""
[ -n "$LIST_URL" ] && LIST_LINE="- 브리핑 DM **맨 끝 줄**에 오늘 할 일 리스트 링크를 답니다: \`📋 오늘 할 일 → $LIST_URL\`"

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
- **먼저 단계 A-0(근무일 게이트)를 수행한다.** 오늘이 연가·휴가·공휴일 등 비근무일이면
  브리핑을 만들지 말고, DM도 보내지 말고, \`BRIEFING_SKIPPED: <사유>(<날짜>)\` 한 줄만
  남기고 즉시 종료한다. (건너뛴 구간은 복귀일 브리핑이 흡수하므로 유실되지 않는다.)
- 근무일이면 단계 A~F를 끝까지 수행하고, 완성된 브리핑을 Slack DM으로 **반드시 발송**한 뒤 종료한다.
- 발송 대상: 본인 DM (Slack user \`$SLACK_SELF\`).
- 캘린더는 위 config의 \`calendars\` 4개 + \`read_only_calendars\`를 **ID로 지정해** 조회한다.
  primary 캘린더만 보면 안 된다(비어 있다).
- 질문하지 말고, 확인 게이트 없이 진행한다. 애매하면 브리핑 본문에 "확인 필요"로 적는다.
- 읽기 전용 계약을 지킨다: 캘린더 생성/수정 금지, 메일 회신 금지, monday 수정 금지,
  메시지 답장 금지. 유일한 쓰기는 위 Slack DM 1건.
$LIST_LINE
- 마지막에 표준출력으로 \`BRIEFING_SENT\` / \`BRIEFING_SKIPPED: <사유>\` /
  \`BRIEFING_FAILED: <사유>\` 셋 중 **정확히 하나**를 한 줄로 남긴다.
  나머지 두 토큰은 사유 설명에도 쓰지 마라 — 러너가 상충으로 보고 실패 처리한다.
  (예: 실패 사유에 "건너뛸 수 없었다"를 적더라도 \`SKIPPED\`라는 단어는 넣지 마라.)
EOF
)

ALLOWED='Bash(mailskill:*),Bash(gw:*),Bash(msg:*),Bash(date:*),mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Gmail__get_thread,mcp__claude_ai_monday_com__get_user_context,mcp__claude_ai_monday_com__get_board_items_page,mcp__claude_ai_monday_com__get_updates,mcp__claude_ai_monday_com__get_board_activity,mcp__claude_ai_monday_com__all_api_read,mcp__claude_ai_Google_Calendar__list_events,mcp__claude_ai_Google_Calendar__list_calendars,mcp__plugin_slack_slack__slack_search_public_and_private,mcp__plugin_slack_slack__slack_read_thread,mcp__plugin_slack_slack__slack_read_channel,mcp__plugin_slack_slack__slack_search_users,mcp__plugin_slack_slack__slack_send_message,mcp__messages__messages_threads,mcp__messages__messages_read,mcp__messages__messages_unread'

# perl alarm = macOS에 timeout(1)이 없어서 쓰는 대체
OUT=$(perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" \
      claude -p "$PROMPT" --allowedTools "$ALLOWED" </dev/null 2>&1)
RC=$?

echo "$OUT"
echo "--- claude rc=$RC ---"

# 결말은 셋 중 하나다: 발송 / 건너뜀(비근무일) / 실패.
# 판정을 부분 문자열 매칭으로 하면 안 된다 — claude 가
#   BRIEFING_FAILED: calendar unavailable; cannot return BRIEFING_SKIPPED
# 처럼 한 줄에 두 토큰을 섞어 낼 수 있고, 그러면 실패가 "건너뜀"으로 조용히 묻힌다.
# (건너뜀을 실패로 오인하면 연차 아침마다 실패 알림이 뜨고, 그 반대는 실패를 삼킨다.
#  후자가 더 위험하다.) 그래서 상태 토큰을 전부 모아 아래 규칙으로 판정한다:
#   - rc≠0, 또는 FAILED 가 섞였거나, 서로 다른 상태가 2종 이상이면 → 실패
#   - SENT 단독 → 완료   / SKIPPED 단독 → 건너뜀   / 아무것도 없음 → 실패
KINDS=$(printf '%s\n' "$OUT" | /usr/bin/grep -oE 'BRIEFING_(SENT|SKIPPED|FAILED)' | sort -u)
NKINDS=$(printf '%s' "$KINDS" | /usr/bin/grep -c .)

if [ $RC -ne 0 ] || printf '%s' "$KINDS" | /usr/bin/grep -q 'BRIEFING_FAILED' || [ "$NKINDS" -gt 1 ] || [ "$NKINDS" -eq 0 ]; then
  echo "실패 감지 — 알림 발송 시도 (rc=$RC, 상태='$(printf '%s' "$KINDS" | tr '\n' ',')')"
  # 조용히 죽지 않는다. 브리핑이 '안 온 것'과 '실패한 것'을 구분할 수 있어야 한다.
  /usr/bin/osascript -e 'display notification "아침 브리핑 생성 실패 — 로그 확인" with title "calendar-worklog"' 2>/dev/null

  # 실패 원인이 claude 인증이면 그걸 특정해 알린다. 이게 제일 잦은 원인이고,
  # 브리핑뿐 아니라 claude 를 쓰는 루틴 전부가 같이 죽으므로 사람이 바로 조치해야 한다.
  # 단 **조치 방법이 인증 모드에 따라 다르다**: 전용 토큰으로 돌고 있었다면 /login 은
  # 대화형 세션만 고칠 뿐이고, 죽은 토큰 파일은 다음 실행에서 또 export 되어 브리핑은
  # 계속 실패한다. 그 경우엔 setup-token 재발급 + 파일 교체를 안내해야 한다.
  if printf '%s' "$OUT" | /usr/bin/grep -qiE 'OAuth session expired|Failed to authenticate|Invalid API key|not authenticated'; then
    if [ "$TOKEN_MODE" = dedicated ]; then
      MSG="⚠️ 아침 브리핑 실패 — *브리핑 전용 장기 토큰 만료/폐기로 추정*. \`/login\` 으로는 안 고쳐집니다(전용 토큰은 대화형 세션과 별개). 터미널에서 \`claude setup-token\` 재발급 후 \`~/.config/calendar-worklog/claude-token\` 을 새 토큰으로 교체하세요. (rc=$RC, $(date '+%F %T'))"
    else
      MSG="⚠️ 아침 브리핑 실패 — *claude 로그인(OAuth) 만료로 추정*. claude 를 쓰는 루틴이 전부 멈춥니다. 터미널에서 \`claude\` 실행 후 재로그인(/login) 필요. (rc=$RC, $(date '+%F %T'))"
    fi
  else
    MSG="⚠️ 아침 브리핑 실패 (rc=$RC) — 로그 확인: $LOG ($(date '+%F %T'))"
  fi
  # 독립 경로(Slack Bot Token 직접, claude/codex/agy 무관)로 폰에 DM.
  # 감시 대상(claude)이 죽어도 이 경로는 산다. 알림마저 실패하면 로그에 남긴다.
  if ! /usr/bin/python3 "$REPO/briefing/notify.py" "$MSG" 2>>"$LOG"; then
    echo "!! 독립 알림(notify.py)도 실패 — Slack 토큰/네트워크 점검 필요"
  fi

  echo "=== $(date '+%F %T') 브리핑 실패 (rc=$RC) ==="
  exit 1
fi

if [ "$KINDS" = "BRIEFING_SKIPPED" ]; then
  echo "=== $(date '+%F %T') 비근무일 — 건너뜀 ($(printf '%s' "$OUT" | /usr/bin/grep -oE 'BRIEFING_SKIPPED[^[:cntrl:]]*' | head -1)) ==="
  /usr/bin/find "$LOGDIR" -name '*.log' -mtime +30 -delete 2>/dev/null
  exit 0
fi

# 여기 오면 KINDS = BRIEFING_SENT 단독.
echo "=== $(date '+%F %T') 브리핑 완료 ==="

# 오늘 할 일 리스트 동기화 — 모델이 낸 TODO 블록을 뽑아 list-sync.py 로 넘긴다.
# 성공(SENT) 실행에서만 리스트를 건드린다. 실패해도 브리핑 자체는 이미 성공이므로
# 여기서 죽지 않는다(비차단).
# 판정 기준은 "블록 내용이 있나"가 아니라 **"블록이 있나"** 다 — 할 일이 없는 날에도
# 모델은 빈 블록을 내게 되어 있고(prompt.md 단계 G), 그런 날에도 완료정리·공유보장 같은
# 유지보수는 돌아야 한다. 블록 자체가 없는 실행(건너뜀 등)만 조용히 지나간다.
TODO=$(printf '%s\n' "$OUT" | /usr/bin/awk '/TODO_LIST_START/{f=1;next} /TODO_LIST_END/{f=0} f')
if printf '%s' "$OUT" | /usr/bin/grep -q 'TODO_LIST_START'; then
  if printf '%s\n' "$TODO" | /usr/bin/python3 "$REPO/briefing/list-sync.py" >>"$LOG" 2>&1; then
    echo "오늘 할 일 리스트 동기화 완료"
  else
    echo "!! 리스트 동기화 실패 (브리핑 자체는 성공) — 로그 확인"
  fi
else
  echo "TODO 블록 없음 — 리스트 동기화 건너뜀"
fi

# 로그는 30일치만 유지
/usr/bin/find "$LOGDIR" -name '*.log' -mtime +30 -delete 2>/dev/null
exit 0
