"""Generates, once, the 'argued for the wrong decision' candidates of the review family.

For every test ad the answer (approve or reject) was fixed when the ad was written. Here the model is asked
to write the review of someone who reached the opposite decision, argued as carefully as a real one. Such a
review is wrong by construction, whatever its wording. A generated review is kept only if it has the required
(wrong) decision and passes every rule check (verbatim quotes, existing clause ids, sound structure), so that
only a judge, not a script, can tell it is wrong. What was dropped is counted by build_items.py.

Usage:  python eval/gen_flips.py        (one batch; writes data/generated/review_flips.jsonl)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from judgecal import llm, prompts, rules  # noqa: E402
import build_items as B  # noqa: E402

OUT = ROOT / "data" / "generated" / "review_flips.jsonl"
STORE = ROOT / "eval" / "results" / "raw" / "flips.jsonl"
CATS = ["ABSOLUTE", "MEDICAL", "GUARANTEE", "DISPARAGE", "DATA", "ALCOHOL", "WEIGHT", "BEFORE_AFTER", "FLAG", "OTHER"]
VIOLATION = {"type": "object", "properties": {
    "category": {"type": "string", "enum": CATS}, "clause_id": {"type": "string"}, "ad_quote": {"type": "string"},
    "visual_evidence": {"type": "string"}, "policy_quote": {"type": "string"}, "explanation": {"type": "string"}},
    "required": ["category", "clause_id", "ad_quote", "visual_evidence", "policy_quote", "explanation"], "additionalProperties": False}
REVIEW = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["approve", "reject"]},
                                           "violations": {"type": "array", "items": VIOLATION}, "notes": {"type": "string"}},
          "required": ["decision", "violations", "notes"], "additionalProperties": False}

SYSTEM = """You write test material for a quality check of ad reviews. For the ad below, write the review of a reviewer who reached the decision stated in the request. That decision is the wrong one for this ad; write the review as carefully argued as a real one, so that a checker has to think to see the mistake. Do not hint that the decision is wrong.

Format rules, which the review must follow exactly:
- decision: the decision stated in the request.
- A "reject" lists exactly one violation: a category, the id of a clause marked "rule" in the library, ad_quote (words copied character for character from the ad; at least four characters), visual_evidence (empty unless the problem is in the picture), policy_quote (words copied character for character from the cited clause), and a one or two sentence explanation.
- An "approve" lists no violation and explains in notes why the wording that might look risky is acceptable; it may refer to guidance clauses by id.
- Write explanations and notes in the language of the ad.

Policy library ({jurisdiction}):

{library}"""


def main() -> int:
    items, ocr, _ = B._review_sources()
    reqs, want = {}, {}
    for aid in sorted(items):
        it = items[aid]
        jur = "CN" if it["lang"] == "zh" else "TikTok"
        material = {"jurisdiction": jur, "ad_text": B.ad_text(it), "image": f"images/{aid}.png" if it["kind"] == "image" else None}
        wrong = "approve" if it["labels"] else "reject"
        content = prompts._ad_blocks(material) + [{"type": "text", "text": f"Decision to argue for: {wrong}"}]
        for n in (1, 2):
            key = f"flip|{aid}|{n}"
            reqs[key] = llm.params(SYSTEM.format(jurisdiction=jur, library=prompts.library_text(jur)), content, REVIEW)
            want[key] = (aid, wrong, material)
    res = llm.run(reqs, STORE)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    kept, why = {}, {}
    for key in sorted(res):
        aid, wrong, material = want[key]
        cand = res[key]["output"]
        if aid in kept or cand is None:
            continue
        probs = rules.review_problems(material, cand)
        if cand["decision"] == wrong and not probs:
            kept[aid] = cand
        else:
            why[aid] = probs or ["decision not the requested one"]
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for aid in sorted(kept):
            f.write(json.dumps({"ad": aid, "review": kept[aid]}, ensure_ascii=False) + "\n")
    missing = sorted(set(a for a, _, _ in want.values()) - set(kept))
    print(f"ads: {len(items)}; usable wrong-decision reviews: {len(kept)}; none usable: {len(missing)}")
    for aid in missing[:20]:
        print("  ", aid, why.get(aid))
    print(llm.total_cost(STORE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
