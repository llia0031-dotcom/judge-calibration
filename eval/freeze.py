"""Writes the hashes of the frozen files into PREREGISTRATION.md (sha256 of the file with LF line endings, first 12 characters).

Usage:  python eval/freeze.py          write the table (only while it is still empty)
        python eval/freeze.py --check  compare the files with the table; exit 1 if any changed
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "eval" / "PREREGISTRATION.md"
FILES = ["judgecal/llm.py", "judgecal/prompts.py", "judgecal/rules.py", "judgecal/stats.py", "judgecal/items.py",
         "eval/build_items.py", "eval/run.py", "eval/qc.py", "eval/gen_flips.py",
         "data/policy/cn.json", "data/generated/review_flips.jsonl",
         "data/items/review.jsonl", "data/items/claim.jsonl", "data/items/suggest.jsonl", "data/items/jv.jsonl",
         "data/items/mqm.jsonl", "data/items/qc.jsonl",
         "private/items/regulator.jsonl", "private/items/summeval.jsonl", "private/policy/tiktok.json"]


def sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]


def table() -> str:
    rows = ["| File | sha256 (12) |", "|---|---|"]
    for f in FILES:
        p = ROOT / f
        rows.append(f"| `{f}` | {sha12(p) if p.exists() else 'not in this copy'} |")
    return "\n".join(rows)


def main() -> int:
    text = PREREG.read_text(encoding="utf-8")
    if "--check" in sys.argv:
        # the public copy replaces the TikTok policy quotes in two files; tools/make_public.py records the
        # frozen hash each of them was made from and the hash of the copy
        # accepted changes: the corrections written in the change log, in order (each with the frozen hash it
        # starts from and the hash it ends at), then the changes the public copy makes to a file
        public = {}
        cc = ROOT / "eval" / "corrections.json"
        if cc.exists():
            for c in json.loads(cc.read_text(encoding="utf-8"))["corrections"]:
                for f, hh in c["files"].items():
                    public[f] = {"from": public.get(f, hh)["from"], "to": hh["to"]}
        pc = ROOT / "eval" / "public_copy.json"
        if pc.exists():
            for f, hh in json.loads(pc.read_text(encoding="utf-8"))["changed"].items():
                start = public[f]["from"] if f in public and public[f]["to"] == hh["from"] else hh["from"]
                public[f] = {"from": start, "to": hh["to"]}
        bad = []
        for f, h in re.findall(r"\| `([^`]+)` \| ([0-9a-f]{12}|not in this copy) \|", text):
            p = ROOT / f
            if not p.exists() or h == "not in this copy":
                continue
            now = sha12(p)
            if now != h and not (f in public and public[f]["from"] == h and public[f]["to"] == now):
                bad.append(f)
        print("changed since the freeze:" if bad else "all frozen files unchanged", *bad, sep="\n  ")
        return 1 if bad else 0
    marker = "(filled in by `eval/freeze.py`)"
    if marker not in text:
        raise SystemExit("the table is already filled in; changes go into the change log")
    PREREG.write_text(text.replace(marker, table()), encoding="utf-8", newline="\n")
    print(table())
    return 0


if __name__ == "__main__":
    sys.exit(main())
