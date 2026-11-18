"""Checks every number in the report and the READMEs against the result files with evidence-check.

For each sentence or table row that states a number, the lines of the sources that contain its numbers are
attached as quotes, and evidence-check's script then confirms two things: every quote is verbatim in its source,
and every number of the sentence is in its quotes. Identifiers that contain digits (model names, clause ids,
item ids, version tags, section numbers, years, file names) are taken out before the check.

Usage:  python tools/check_numbers.py [files...]     default: the report and both READMEs
Writes eval/results/claims.json (the claims with their quotes) and exits 1 if any claim is not supported.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evcheck import _rules as ev

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "eval" / "results" / "RESULTS.md", ROOT / "eval" / "PREREGISTRATION.md", ROOT / "eval" / "results" / "key_issues.json",
           ROOT / "data" / "items" / "LICENSES.md"]
DRAFTS = [ROOT / "eval" / "EVALUATION.md", ROOT / "README.md", ROOT / "README.zh-CN.md"]

IDENTIFIERS = [
    r"\]\([^)]*\)",                                  # link targets
    r"`[^`]*`",                                      # code, file names, ids
    r"claude-[a-z]+-\d+-\d+",                        # model names
    r"\b[A-Z]{2}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b",        # clause ids
    r"\b(?:qc|rev|clm|sug|reg|jv|se|mqm)-[\w-]+",     # item ids
    r"\bv\d\b", r"\bS[123]\b", r"\b[A-C]\b(?=[ ,:)])",  # version tags, standard parts, arms
    r"(?:[Ss]ection|§|第)\s?\d+(?:\.\d+)?(?:\s?节)?", r"\b\d+(?:\.\d+)? of the plan\b",
    r"\b(?:19|20)\d\d\b", r"WMT \d+", r"Python \d+\.\d+", r"BY-SA \d\.\d|CC BY-SA \d\.\d|Apache-\d\.\d|BSD-\d-Clause",
    r"\bA\d\b", r"pH", r"SPF \d+",
]


def strip_ids(text: str) -> str:
    for p in IDENTIFIERS:
        text = re.sub(p, " ", text)
    return text


def units(path: Path):
    """(line number, text) for each table row and each sentence of the prose, skipping headings and code."""
    in_code = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line.strip() or line.startswith("#") or re.match(r"^\|[-| ]+\|$", line):
            continue
        if line.startswith("|"):
            yield n, line
            continue
        for s in re.split(r"(?<=[.!?。！？])\s+(?=[A-Z0-9(“\"「（])|(?<=[。！？；])", line):
            if s.strip():
                yield n, s


def main() -> int:
    drafts = [Path(a) for a in sys.argv[1:]] or DRAFTS
    sources = ev.load_sources([str(p) for p in SOURCES if p.exists()])
    lines = [(sid, l.strip()) for sid, s in sources.items() for l in s.text.splitlines() if len(l.strip()) >= 6]
    claims, unmatched = [], []
    for d in drafts:
        for n, text in units(d):
            clean = strip_ids(text)
            need = ev.numbers_in(clean)
            if not need:
                continue
            chosen, left = [], set(need)
            while left:
                best = max(lines, key=lambda x: len(left & ev.numbers_in(x[1], generous=True)))
                got = left & ev.numbers_in(best[1], generous=True)
                if not got:
                    break
                chosen.append(best)
                left -= got
            cid = f"{d.name}:{n}:{len(claims)}"
            claims.append({"id": cid, "text": clean, "evidence": [{"source": sid, "quote": q} for sid, q in chosen]})
            if left:
                unmatched.append((cid, text.strip()[:160], sorted(left)))
    res = ev.check(claims, sources)
    bad = [r for r in res["claims"] if r["status"] != "supported"]
    out = ROOT / "eval" / "results" / "claims.json"
    out.write_text(json.dumps({"claims": claims, "summary": res["summary"]}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"{res['summary']['claims']} sentences with numbers; {res['summary']['supported']} supported; {len(bad)} not")
    for r in bad:
        why = ", ".join(r["problems"]) + (f"; missing {r['missing_numbers']}" if r["missing_numbers"] else "")
        print(f"  {r['id']}: {why}\n      {r['text'].strip()[:200]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
