"""Section 7.10: a second judge, claude-sonnet-5-5, on 120 test items (40 each of claim, suggest and mqm, chosen
by hash), one judgment each, same prompts and effort as the main judge.

  python eval/second.py estimate    five live calls; prints the cost per call and the estimate for 120
  python eval/second.py run         the 120 requests as one batch (eval/results/raw/second.jsonl)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judgecal import llm, prompts  # noqa: E402
from judgecal.items import h, load_all  # noqa: E402

MODEL = "claude-sonnet-5-5"
PER_FAMILY = 40


def pick(items):
    out = []
    for fam in ("claim", "suggest", "mqm"):
        its = sorted((i for i in items if i["family"] == fam and i["split"] == "test"), key=lambda i: h("second:" + i["id"]))
        out += its[:PER_FAMILY]
    return out


def requests(items):
    a = json.loads((ROOT / "eval" / "adopted.json").read_text(encoding="utf-8"))["version"]
    reqs = {}
    for it in pick(items):
        v = a if it["family"] in prompts.BINARY else "fixed"
        system, content, schema = prompts.request(it, v)
        reqs[f"second|{it['id']}|{v}"] = llm.params(system, content, schema, model=MODEL)
    return reqs


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "estimate"
    reqs = requests(load_all())
    if cmd == "estimate":
        keys = list(reqs)[::24][:5]
        res = llm.run({k: reqs[k] for k in keys}, ROOT / "eval" / "results" / "raw" / "second-estimate.jsonl", batch=False)
        per = sum(r["cost_usd"] for r in res.values()) / len(res)
        print(f"{len(res)} live calls, {per:.5f} USD per call at the standard price; 120 calls at the batch price: about {per / 2 * len(reqs):.3f} USD")
        return 0
    store = ROOT / "eval" / "results" / "raw" / "second.jsonl"
    llm.run(reqs, store)
    print(llm.total_cost(store))
    return 0


if __name__ == "__main__":
    sys.exit(main())
