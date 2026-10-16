#!/usr/bin/env python3
"""주간 과제 보고 — 무인 루틴용 캘린더 읽기 모듈.

calendar@ji.re.kr(전 구성원 [과제]/[업무]/[근태]/[기타] 캘린더의 writer)의
**readonly OAuth refresh token**으로 구성원 캘린더를 읽는다.
서비스계정 키(DWD)를 쓰지 않으므로 조직정책(disableServiceAccountKeyCreation)과 무관하고,
클라우드(/schedule) env에 올라가는 건 broad 권한 키가 아니라 revoke 가능한 readonly 토큰뿐.

필요 env:
  CAL_CLIENT_ID / CAL_CLIENT_SECRET / CAL_REFRESH_TOKEN  — OAuth(설치형, 동의화면 Internal)
  MEMBER_CALENDAR_IDS  — 읽을 캘린더 ID들. JSON 배열 문자열 또는 파일경로(둘 다 허용).
  WEEK_MIN / WEEK_MAX  — ISO8601(+09:00 권장). 예: 2026-06-15T00:00:00+09:00
  OUTFILE              — (선택) 결과 JSON 저장경로. 없으면 stdout.

출력: [{id, summary, tag, member, events:[{summary,start,end,location,description}]}]
  summary 예 "[과제] 고선영" → tag="[과제]", member="고선영" 자동 파싱.
  읽기에 실패한 캘린더는 events=[] 에 **`error` 필드**가 붙는다. 읽는 쪽은 이것을
  "일정 없음"이 아니라 "읽지 못함"으로 구분해야 한다(그러지 않으면 조용히 사람이 빠진다).

종료코드: 전 캘린더를 하나도 읽지 못하면 **1**. 권한·토큰 문제로 통째로 막힌 경우
  빈 보고를 만들어 올리는 것보다 요란하게 죽는 쪽이 낫다. 일부만 실패하면 0 으로 끝내되
  실패분은 `error` 로 남긴다.
"""
import os
import sys
import json

# Apply DNS/connection hang bypass patch for JRI office network
try:
    from . import google_dns_patch
except ImportError:
    try:
        import google_dns_patch
    except ImportError:
        pass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
TAGS = ("[과제]", "[업무]", "[근태]", "[기타]")


def _load_ids(raw: str):
    """MEMBER_CALENDAR_IDS: JSON 배열 문자열이거나 그런 파일의 경로."""
    raw = raw.strip()
    if raw and not raw.lstrip().startswith("["):
        # 파일 경로로 간주
        with open(os.path.expanduser(raw), encoding="utf-8") as f:
            raw = f.read()
    ids = json.loads(raw)
    if not isinstance(ids, list):
        raise ValueError("MEMBER_CALENDAR_IDS must be a JSON array of calendar IDs")
    return ids


def _service():
    missing = [k for k in ("CAL_CLIENT_ID", "CAL_CLIENT_SECRET", "CAL_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        sys.exit(f"missing env: {', '.join(missing)}")
    creds = Credentials(
        token=None,
        refresh_token=os.environ["CAL_REFRESH_TOKEN"],
        client_id=os.environ["CAL_CLIENT_ID"],
        client_secret=os.environ["CAL_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _fetch_events(svc, cid: str, week_min: str, week_max: str):
    evs = []
    page = None
    while True:
        resp = svc.events().list(
            calendarId=cid, timeMin=week_min, timeMax=week_max,
            singleEvents=True, orderBy="startTime", maxResults=250, pageToken=page,
        ).execute()
        for e in resp.get("items", []):
            evs.append({
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "location": e.get("location", ""),
                "description": e.get("description", ""),
            })
        page = resp.get("nextPageToken")
        if not page:
            return evs


def _parse_summary(summary: str):
    for t in TAGS:
        if summary.startswith(t):
            return t, summary[len(t):].strip()
    return "", summary


def main():
    week_min = os.environ.get("WEEK_MIN")
    week_max = os.environ.get("WEEK_MAX")
    if not (week_min and week_max):
        sys.exit("missing env: WEEK_MIN / WEEK_MAX (ISO8601)")
    ids = _load_ids(os.environ.get("MEMBER_CALENDAR_IDS", ""))
    svc = _service()

    out = []
    errors = []
    for cid in ids:
        try:
            summary = svc.calendars().get(calendarId=cid).execute().get("summary", cid)
        except Exception as e:  # noqa: BLE001
            print(f"  ! calendars.get failed {cid[:20]}…: {str(e)[:80]}", file=sys.stderr)
            summary = cid
        tag, member = _parse_summary(summary)
        try:
            evs = _fetch_events(svc, cid, week_min, week_max)
        except Exception as e:  # noqa: BLE001
            # 여기서 죽이지 않는다. 한 캘린더가 막혔다고 나머지 보고까지 날리면 손해가 더 크다.
            # 대신 error 를 달아 "일정 없음"과 구분되게 남긴다.
            reason = str(e)[:200]
            print(f"  ! events.list failed {cid[:20]}…: {reason[:80]}", file=sys.stderr)
            errors.append((cid, reason))
            out.append({"id": cid, "summary": summary, "tag": tag, "member": member,
                        "events": [], "error": reason})
            continue
        out.append({"id": cid, "summary": summary, "tag": tag, "member": member, "events": evs})

    if ids and len(errors) == len(ids):
        # 전부 실패 = 토큰 만료·권한 회수·정책 차단 같은 전역 원인이다. 빈 덤프를 넘기면
        # 보고가 "전원 기록 없음"으로 조용히 완성되므로, 여기서 끊는다.
        sys.exit(f"all {len(ids)} calendars failed to read — {errors[0][1]}")

    payload = json.dumps(out, ensure_ascii=False, indent=1)
    outfile = os.environ.get("OUTFILE")
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(payload)
        n = sum(len(o["events"]) for o in out)
        failed = f", {len(errors)} unreadable" if errors else ""
        print(f"wrote {outfile}: {len(out)} calendars, {n} events{failed}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
