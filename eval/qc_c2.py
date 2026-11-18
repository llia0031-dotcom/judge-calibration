"""Correction 2 (see the change log of PREREGISTRATION.md): the quality-check agent on the test records that
changed when six answer keys got the required-statement label the source added. Same agent, prompt and tools as
eval/qc.py; the registered answers in eval/results/qc-agent.jsonl stay as they are.

Usage:  python eval/qc_c2.py        writes eval/results/qc-agent-c2.jsonl (fewer than 20 requests: ordinary calls)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
import qc as Q  # noqa: E402


def read(path: Path) -> dict[str, dict]:
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def changed() -> list[dict]:
    new = read(ROOT / "data" / "items" / "qc.jsonl")
    old = read(ROOT / "data" / "items" / "archive" / "qc.registered.jsonl")
    return [r for i, r in new.items() if r["split"] == "test" and r != old.get(i)]


def main() -> int:
    recs = changed()
    print("changed test records:", [r["id"] for r in recs])
    res = Q.agent_run(recs, "qc-c2")
    path = ROOT / "eval" / "results" / "qc-agent-c2.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps({"id": r["id"], **res[r["id"]]}, ensure_ascii=False) + "\n")
    for r in recs:
        o = res[r["id"]]["output"] or {}
        print(r["id"], r["truth"], r["dimension"], "->", o.get("verdict"), o.get("problem"), "|", (o.get("reason") or "")[:150])
    print(round(sum(v["usage"]["cost_usd"] for v in res.values()), 4), "USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
