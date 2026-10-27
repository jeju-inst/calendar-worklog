#!/usr/bin/env python3
"""core/prompt.md(에이전트 중립 사본)와 플러그인 스킬(SKILL.md + references/)의 어긋남을 찾는다.

두 벌은 일부러 따로 둔다 — 채팅 트랙(ChatGPT·Claude Project 지식 업로드)은 core/prompt.md 한 파일만
받을 수 있고, 플러그인은 호출당 분량 때문에 references/ 로 나뉘어 있다. 대신 한쪽만 고치고 다른 쪽을
잊는 것을 여기서 잡는다.

검사하는 것:
  1. 워크플로·단계 제목 — 한쪽에만 있는 절
  2. "핵심 규칙 문장" — 굵게 쓴 문장, 또는 금지·의무 표현이 든 문장이 한쪽에만 있는 것.
     두 벌은 문장을 따로 다듬어 왔으므로 같은 워크플로 안에 비슷한 문장(유사도 SIMILAR 이상)이
     있으면 같은 규칙으로 본다. 단계 번호가 갈라진 경우(0-A-2 ↔ A-1-1)도 있어 단계가 아니라
     워크플로 단위로 찾는다.

의도적인 차이는 scripts/prompt-sync-exceptions.json 에 근거와 함께 적는다.
기본은 경고만 하고 exit 0. --strict 면 경고가 있을 때 exit 1.
"""
import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core" / "prompt.md"
SKILL_DIR = ROOT / "plugin" / "skills" / "calendar-worklog"
EXCEPTIONS = Path(__file__).resolve().parent / "prompt-sync-exceptions.json"

# 금지·의무를 담은 문장. 이 표현이 든 문장은 굵게 쓰지 않았어도 핵심 규칙으로 본다.
RULE_WORDS = ("금지", "반드시", "절대", "하지 않", "않습니다", "않는다", "않음", "말 것", "마십시오", "말고")
SIMILAR = 0.55
TOP_SECTIONS = ("능력 매핑", "설정 로드", "공통 출력 규칙", "보안/프라이버시", "실패 처리")


def norm(s):
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"^\s*(?:[-*>]|\d+[.)])\s+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def section_key(level, title):
    """제목을 두 파일 사이에서 맞출 수 있는 키로. 맞출 대상이 아니면 None."""
    title = norm(title)
    if level == 2:
        m = re.match(r"워크플로 (\d+)", title)
        if m:
            return f"WF{m.group(1)}"
        for t in TOP_SECTIONS:
            if title.startswith(t):
                return t
        if title.startswith("네트워크 연결"):
            return "네트워크"
        return None
    if level == 3:
        m = re.match(r"(단계 [A-Z]|\d-[A-Z](?:-\d)?)\b", title)
        return m.group(1) if m else None
    return None


def parse(paths):
    """{(워크플로키, 단계키): [문장...]} 와 각 절의 제목을 돌려준다."""
    sections, titles = {}, {}
    for path in paths:
        wf, step, fence, unit = None, None, False, None
        lines = path.read_text(encoding="utf-8").splitlines()

        def flush():
            nonlocal unit
            if unit and wf:
                sections.setdefault((wf, step), []).append(norm(unit))
            unit = None

        for line in lines:
            if line.strip().startswith("```"):
                flush()
                fence = not fence
                continue
            if fence:
                continue
            m = re.match(r"^(#{1,6})\s+(.*)", line)
            if m:
                flush()
                level = len(m.group(1))
                key = section_key(level, m.group(2))
                if level == 2:
                    wf, step = key, None
                    if key:
                        titles[(wf, None)] = norm(m.group(2))
                elif level == 3 and wf and key:
                    step = key
                    titles[(wf, step)] = norm(m.group(2))
                continue
            if not line.strip():
                flush()
                continue
            # 새 bullet·번호·표 줄이면 새 문장, 아니면 앞 문장의 줄바꿈 이어짐
            if re.match(r"^\s*(?:[-*>|]|\d+[.)])\s", line) or unit is None:
                flush()
                unit = line
            else:
                unit += " " + line.strip()
        flush()
    return sections, titles


def strip_md(u):
    return re.sub(r"[*`_]", "", u)


def has_similar(u, candidates):
    a = strip_md(u)
    for c in candidates:
        m = difflib.SequenceMatcher(None, a, strip_md(c), autojunk=False)
        if m.real_quick_ratio() >= SIMILAR and m.quick_ratio() >= SIMILAR and m.ratio() >= SIMILAR:
            return True
    return False


def by_workflow(sections):
    out = {}
    for (wf, _), units in sections.items():
        out.setdefault(wf, []).extend(units)
    return out


def is_rule(u):
    return "**" in u or any(w in u for w in RULE_WORDS)


def load_exceptions():
    if not EXCEPTIONS.exists():
        return []
    return json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["exceptions"]


def excepted(exc, kind, side, wf, step, text=""):
    for e in exc:
        if e.get("kind", kind) != kind or e.get("side", side) not in (side, "both"):
            continue
        if e.get("workflow") not in (None, wf):
            continue
        if "step" in e and e["step"] != step:
            continue
        if e.get("contains") and e["contains"] not in text:
            continue
        e["_used"] = True
        return True
    return False


def label(wf, step):
    return wf + (f" / {step}" if step else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="경고가 있으면 exit 1")
    args = ap.parse_args()

    plugin_files = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))
    core, core_titles = parse([CORE])
    plug, plug_titles = parse(plugin_files)
    exc = load_exceptions()
    warnings = []

    for side, mine, theirs, titles in (("core", core, plug, core_titles), ("plugin", plug, core, plug_titles)):
        other = "plugin" if side == "core" else "core"
        their_wf = by_workflow(theirs)
        for key in sorted(mine, key=str):
            wf, step = key
            if key not in theirs:
                if not excepted(exc, "section", side, wf, step):
                    warnings.append(f"[절] {label(wf, step)} — {side} 에만 있음: {titles.get(key, '')}")
                if wf not in their_wf:
                    continue
            pool = their_wf.get(wf, [])
            for u in mine[key]:
                if is_rule(u) and not has_similar(u, pool) and not excepted(exc, "line", side, wf, step, u):
                    warnings.append(f"[규칙] {label(wf, step)} — {side} 에만 있음({other} 에 같은 문장 없음): {u[:140]}")

    unused = [e for e in exc if not e.get("_used")]
    for w in warnings:
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title=prompt-sync::{w}")
        else:
            print("경고:", w)
    for e in unused:
        print(f"참고: 쓰이지 않는 예외 — {e.get('workflow')}/{e.get('step')} {e.get('contains', '')[:60]}")
    print(f"prompt-sync: 경고 {len(warnings)}건, 예외 {len(exc) - len(unused)}/{len(exc)}건 적용")
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
