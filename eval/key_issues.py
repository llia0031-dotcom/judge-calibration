"""Disagreements that trace to the answer key (post hoc, after scoring; changes no score).

For every right candidate the judge failed (majority of three), and every correct record the QC agent flagged,
this script tests one stated fact with a string check, so that the report can say which disagreements point at
the answer key rather than at the judge. It adjudicates nothing else. Writes eval/results/key_issues.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judgecal.items import load_all  # noqa: E402

# (item, what is tested, words that must be absent from the material for the fact to hold)
ABSENT_WORDS = [
    ("sug-v1-P11-c3-good", "the suggestion names a pH of 5.5", ["5.5"]),
    ("sug-zh-Z07-c2-good", "the rewrite says the food is made to order (现做)", ["现做"]),
    ("sug-mixed2-N08-c2-good", "the rewrite calls the serum lightweight", ["light"]),
]
# stored reviews the judge failed because of a violation the answer key does not list
EXTRA_VIOLATION = ["rev-en-t08-ok1", "rev-en-t48-ok1"]
# correct QC records the agent flagged for a violation the record does not list; tested: the clause text
# contains the statement the agent says is missing
MISSING_STATEMENT = [("qc-zh-t08-key", "CN-AL-18", "本品不能代替药物")]


def main() -> int:
    items = {i["id"]: i for i in load_all()}
    qc = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "items" / "qc.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    out = {"absent_words": [], "extra_violation": [], "missing_statement": []}
    for iid, what, words in ABSENT_WORDS:
        it = items[iid]
        blob = json.dumps(it["material"], ensure_ascii=False).lower()
        cand = json.dumps(it["candidate"], ensure_ascii=False).lower()
        holds = all(w.lower() in cand and w.lower() not in blob for w in words)
        out["absent_words"].append({"item": iid, "fact": f"{what}; the word is in the candidate and in neither the listing nor the evidence", "holds": holds})
    for iid in EXTRA_VIOLATION:
        it = items[iid]
        key = qc[f"qc-{it['cluster']}-key"]["candidate"]["labels"]
        listed = it["candidate"]["violations"]
        no_quote = [v for v in listed if not v["ad_quote"].strip()]
        key_no_span = [l for l in key if not l.get("span")]
        holds = len(no_quote) > len(key_no_span)
        out["extra_violation"].append({"item": iid, "fact": f"the review lists {len(listed)} violations, {len(no_quote)} of them about something the ad leaves out; the answer key lists {len(key)}, {len(key_no_span)} of that kind", "holds": holds})
    from judgecal import rules

    for rid, clause, words in MISSING_STATEMENT:
        r = qc[rid]
        text = {c["id"]: c for c in rules.policy(r["material"]["jurisdiction"])["clauses"]}[clause].get("text", "")
        holds = words in text and words not in r["material"]["ad_text"]
        out["missing_statement"].append({"item": rid, "fact": f"{clause} requires the statement 「{words}」 and the ad does not carry it", "holds": holds})
    path = ROOT / "eval" / "results" / "key_issues.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
