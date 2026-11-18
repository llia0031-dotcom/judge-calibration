"""How often the rule layer flags answers that are right in substance (no model calls).

The item set keeps a stored review or verdict as a right candidate only if it passes the rule checks, so on
the items themselves the rule layer has no false alarms by construction. This script counts, on the stored
answers of the source projects before that filter, how many substantively right answers the rule checks
would have flagged, and why. Needs the source folders (see build_items.py). Writes eval/results/source_stats.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from judgecal import rules  # noqa: E402
import build_items as B  # noqa: E402


def main() -> int:
    items, ocr, rows = B._review_sources()
    n = flagged = 0
    why = Counter()
    for r in rows:
        it = items[r["item"]]
        if it["split"] == "dev":
            continue
        cand = {k: r["output"][k] for k in ("decision", "violations", "notes")}
        if not B.strictly_right(it, cand):
            continue
        material = {"jurisdiction": "CN" if it["lang"] == "zh" else "TikTok", "ad_text": B.ad_text(it)}
        n += 1
        p = rules.review_problems(material, cand)
        if p:
            flagged += 1
            why.update(p)
    src = B.SRC["claim"]
    base = json.loads((src / "eval" / "verify" / "items.json").read_text(encoding="utf-8"))["items"]
    inst = {i["id"]: i for i in json.loads((src / "data" / "v3" / "instances" / "index.json").read_text(encoding="utf-8"))["instances"]}
    resume = {k: (src / "data" / "v3" / "instances" / v["file"]).read_text(encoding="utf-8").strip() for k, v in inst.items()}
    cn = cf = 0
    cwhy = Counter()
    for b in base:
        if b["kind"] != "right":
            continue
        cn += 1
        p = rules.claim_problems({"resume": resume[b["resume"]]}, {"resume_fact": b["resume_fact"], "quotes": b["quotes"]})
        if p:
            cf += 1
            cwhy.update(p)
    out = {"review": {"stored_right_reviews": n, "flagged_by_rules": flagged, "reasons": dict(why)},
           "claim": {"right_verdicts": cn, "flagged_by_rules": cf, "reasons": dict(cwhy)}}
    (ROOT / "eval" / "results" / "source_stats.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
