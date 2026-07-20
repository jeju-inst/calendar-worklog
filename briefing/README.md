# briefing — 아침 브리핑 (매 평일 08:00)

메일·문자·Slack·monday·캘린더를 훑어 **오늘 할 일**을 정리해 본인 Slack DM으로 보낸다.
worklog 본체(`core/prompt.md`)가 *어제 뭐 했나*를 캘린더에 기록한다면, 이쪽은 *오늘 뭐
하나*를 정리해 전달한다.

## 읽기 전용 계약

이 워크플로는 **아무것도 바꾸지 않는다.** 캘린더 이벤트를 만들지 않고, 메일에 회신하지
않고, monday item을 수정하지 않고, 메시지에 답장하지 않는다. 유일한 쓰기는 **본인에게
보내는 Slack DM 1건**이다.

이게 사람 확인 없이 08:00에 무인 실행해도 되는 근거다. 쓰기 동작을 추가하려면 무인 실행
전제부터 다시 봐야 한다.

## 구성

| 파일 | 역할 |
|---|---|
| `prompt.md` | 브리핑 워크플로 (단계 A~F + 순위 기준) |
| `run-briefing.sh` | launchd가 부르는 러너. 프롬프트 조립 + `claude -p` 실행 + 실패 알림 |
| `com.namun.morning-briefing.plist` | launchd 스케줄 (평일 08:00) |
| `logs/` | 일자별 실행 로그 (30일 보관, gitignore) |

## 소스와 백엔드

| 소스 | 접근 | 커넥터 있음? |
|---|---|---|
| 캘린더 | Google Calendar 커넥터 | ✅ |
| Slack | Slack MCP | ✅ |
| monday | monday.com 커넥터 | ✅ |
| 문자/iMessage | `msg` (messages-cli MCP) | 로컬 전용 |
| **메일 (ji.re.kr)** | `mailskill` 5동사 계약 | **❌ 웍스모바일 — 커넥터 없음** |

메일만 커넥터 경로가 없어서 로컬 어댑터가 필수다. 프롬프트는 `mailskill`의 계약
(`accounts/list/search/read/reply`)만 호출하고 himalaya·IMAP 같은 구현을 가정하지
않으므로, 백엔드가 교체돼도 프롬프트는 안 바뀐다. 전사 배포 논의는 `~/dev/mail-skill`.

## 실행 위치가 소스를 가른다

문자·메일은 로컬 바이너리라 **클라우드 `/schedule` 루틴으로는 못 읽는다.** 그래서 주간
과제 보고(`automation/`)는 클라우드인데 브리핑은 로컬 launchd다. 08:00은 맥이 켜져 있는
시각이라 이게 오히려 자연스럽다.

## 설치

```sh
cp briefing/com.namun.morning-briefing.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.namun.morning-briefing.plist
launchctl print gui/$(id -u)/com.namun.morning-briefing | head -20   # 확인
```

제거:
```sh
launchctl bootout gui/$(id -u)/com.namun.morning-briefing
rm ~/Library/LaunchAgents/com.namun.morning-briefing.plist
```

수동 실행 (스케줄 무관, 지금 바로):
```sh
./briefing/run-briefing.sh && tail -40 briefing/logs/$(date +%F).log
```

launchd 환경을 흉내내서 돌려보려면:
```sh
env -i HOME=$HOME USER=$USER PATH=/usr/bin:/bin ./briefing/run-briefing.sh
```

## 실측 (2026-07-20)

`env -i`로 환경을 벗긴 상태에서 5소스 전부 가용 확인:

```
MONDAY=조남운
SLACK=조남운 (지속성장/AI센터)
CAL=0        ← primary만 봐서 0. 4개 그룹 캘린더는 별도 확인: 과제3·근태8·업무6·공식1
MAIL=7월　제주연구원　급여명세서
MSG=햇볕
```

claude.ai 커넥터(monday·캘린더)가 헤드리스에서 안 뜰 것을 우려했으나 **전부 떴다.**
launchd 유저 에이전트는 사용자 Aqua 세션에서 돌아 키체인에 접근되기 때문으로 보인다.

**주의**: `CAL=0`이 보여주듯 primary 캘린더만 보면 비어 있다. 러너가 `user-config.yaml`을
프롬프트에 통째로 먹여 4개 캘린더 ID를 지정 조회하게 하는 이유다.

## 메일 계정 역할 분담

업무는 전부 회사 메일(`ji`)로 오지만 **연구·논문 트래픽은 기관 계정으로 온다.** 그래서
계정마다 다르게 훑는다 (`prompt.md` 단계 C-1).

| 계정 | 상태 (2026-07-20) | 브리핑에서 |
|---|---|---|
| `ji` (웍스모바일) | ✅ mailskill | 업무 — 전량 |
| **`namun.cho@gmail.com`** | ✅ Gmail 커넥터 | **연구 주력** — 신호만 필터 |
| `kias` 고등과학원 | ✅ mailskill | 연구 보조 |
| `korea` 고려대 | ✅ mailskill | 연구 보조 |
| `snu` | ❌ `Invalid credentials` | 제외 |
| `naver-m` | ❌ 앱비번 거부 | 제외 |
| `kakao` | ❌ 키체인 조회 실패 | 제외 |
| Maildir 계정 다수 | 과거 아카이브 | 대상 아님 |

깨진 3개는 앱비번 재발급이 필요하다. 살아나면 연구 계정으로 편입할지 판단.

### gmail은 IMAP으로 옮기는 게 낫다 (미완)

현재 연구 주력 계정만 **Gmail 커넥터**를 쓴다. 작동은 하지만(헤드리스 실측 통과,
`ACCT=namun.cho@gmail.com`) 계약이 mailskill 5동사와 달라 프롬프트에 백엔드 분기가 생기고,
**claude.ai 토큰이 만료되면 연구 섹션이 조용히 사라진다.** 매일 무인 실행되는 도구에서
가장 피해야 할 실패 모드다.

그래서 프롬프트는 **백엔드 우선순위**로 써 뒀다:
1. `mailskill accounts` 에 gmail 계정이 있으면 그것
2. 없으면 Gmail 커넥터로 폴백

즉 `~/dev/mail-skill-namun` 에 gmail IMAP 계정(앱비번)을 추가하면 **이 프롬프트를 고치지
않아도** 자동으로 계약 경로로 넘어간다. 그게 끝나면 러너의 `--allowedTools` 에서
`mcp__claude_ai_Gmail__*` 를 빼도 된다.

### 어댑터 stdout 오염 — 해결됨 (2026-07-20)

증상은 `mailskill list korea` 출력에 WARN이 섞여 파싱이 계정마다 랜덤하게 깨지는 것이었다.

진단해보니 himalaya는 결백했다 — WARN은 **이미 stderr로** 잘 나가고 있었다. 진짜 원인은
러너가 `Bash(mailskill:*)`로 호출하고 **에이전트의 Bash 도구가 두 스트림을 합쳐서** 넘긴다는
것. 즉 "stdout 오염"이 아니라 "합쳐진 스트림"이 문제였다.

`~/dev/mail-skill-namun/bin/mailskill` 에서 세 가지를 고쳤다:

1. `RUST_LOG=off` 로 백엔드 로그를 **원천 차단** — 합쳐 받아도 JSON만 남는다.
   (`MAILSKILL_LOG=debug` 로 되살릴 수 있고, 그때도 로그는 stderr로만 간다.)
2. JSON 동사에 검증 래퍼를 씌워 **stdout이 JSON일 때만 통과**시킨다. himalaya v1.2.0은
   쿼리 파스 에러에도 exit 0을 내는데, 이걸 exit 1로 승격했다 — 그전엔 호출측이
   "빈 결과"와 "깨진 호출"을 구분할 수 없었다.
3. `search`/`list` 에 `-f <폴더>` 를 노출 — worklog가 보낸편지함을 봐야 하는데
   계약에 폴더 지정 통로가 아예 없었다.

덤으로 문서의 검색 문법이 틀려 있던 것도 고쳤다(`since` 는 himalaya에 존재하지 않는
조건이라 그 예제는 항상 실패했다 — 게다가 exit 0이라 조용히 실패했다).

**남은 규약**: stdout이 비면 "메일 없음"이 아니라 **호출 실패**다(빈 결과는 `[]`).
그 계정을 실패로 표시해 누락 목록에 올린다. 조용한 0건이 이 도구의 최악 실패 모드다.

### 회사 메일(`ji`) 날짜 검색이 계속 0건이었던 건 — 해결됨 (2026-07-20)

위 점검 중에 **더 심각한 걸 발견했다.** `ji`(웍스모바일)의 날짜 검색이 **에러 없이 항상
0건**을 반환하고 있었다. 제일 중요한 계정인데.

원인은 IMAP 검색어 불일치였다. himalaya는 날짜 조건을 **`SENTSINCE`**(= `Date:` 헤더 기준)
로만 보내는데, 웍스모바일 서버는 이 검색어를 **거부하지 않고 받아준 뒤 늘 0건**을 답한다
(Date 헤더를 색인하지 않음). 같은 서버에서 `SINCE`(= 서버 수신일 기준)는 정상이다.
원시 IMAP으로 대조하니 `SINCE 01-Jul-2026` = **57건**, `SENTSINCE 01-Jul-2026` = **0건**.
서버가 `OK 0건`이라 답하므로 himalaya도, 어댑터도, 프롬프트도 아무 이상을 못 느낀다.

**즉 worklog가 `ji`에서 메일을 소스로 쓴 적이 사실상 없다.** SKILL.md가 지시하던 쿼리가
정확히 그 형태였고, 게다가 그 예제는 `since`라는 존재하지 않는 조건까지 쓰고 있었다.

어댑터가 **서버 날짜 검색이 0건이면 클라이언트측으로 자동 재확인**하도록 고쳤다
(`~/dev/mail-skill-namun/scripts/date-search.py`). 검증: `after 2026-06-30` → **57건**으로
원시 IMAP 실측과 정확히 일치. 보낸편지함도 동작. 회귀 17/17.

> 교훈: **"에러 없음"은 "정상"이 아니다.** 이 건은 아무 로그도 남기지 않았고,
> 실측 대조(원시 IMAP)를 하기 전까지는 발견될 수 없었다.

## 실패 모드

이 도구의 제일 위험한 실패는 **소스가 빠진 채 조용히 완성된 브리핑**이다. "할 일 없음"으로
오독돼 실제로 놓친다. 그래서:

- 소스 하나가 실패하면 나머지로 완성하되 **브리핑 마지막 줄에 누락 소스를 명시**한다.
- 러너가 `BRIEFING_SENT`를 못 받으면 macOS 알림을 띄운다. 브리핑이 *안 온 것*과
  *실패한 것*을 구분할 수 있어야 한다.
- 캘린더조차 못 읽으면 브리핑이 성립하지 않으므로 실패 보고만 한다.

## 알려진 한계

- **공휴일**: launchd는 평일만 걸지만 법정공휴일은 모른다. 브리핑은 그날도 나간다
  (프롬프트가 캘린더에서 연가·공휴일을 보고 시간창은 맞게 잡지만, 발송 자체는 함).
- **맥이 자고 있으면** 08:00에 안 돌고 깨어난 뒤 실행된다.
- monday 커넥터는 claude.ai 인증에 의존한다. 토큰이 만료되면 monday 섹션만 빠지고
  누락으로 표시된다.
