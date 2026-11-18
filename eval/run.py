"""Sends the judging requests of one stage (Message Batches) and stores the answers. Scoring is score.py.

Stages, in the order they are run:
  dev      v1-v4 (and any later version) on the development split of the three families with planted
           errors; one judgment each. Decides which prompt version is adopted (see PREREGISTRATION.md).
  main     the adopted version on every test item, three judgments each; the fixed prompts of the
           regulator and human-rated families, three judgments each; v1 once as the baseline.
  perturb  the adopted version once more on a fixed subsample with one thing changed at a time:
           rubric wording r1, rubric wording r2, answer options in the other order, content-free text
           added to the candidate (long; assertive), and lower effort.
  pair     a right and a wrong candidate for the same material side by side, in both orders.
  list     all verdicts about one resume in one request, in two orders.

Usage:  python eval/run.py <stage> [--versions v1,v2] [--dry]
Answers already in eval/results/raw/<stage>.jsonl are not asked for again.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judgecal import llm, prompts  # noqa: E402
from judgecal.items import h, load_all  # noqa: E402

RAW = ROOT / "eval" / "results" / "raw"
ADOPTED = ROOT / "eval" / "adopted.json"
REPEATS = 3
FIXED = ("regulator", "jv", "summeval", "mqm")


def adopted() -> str:
    return json.loads(ADOPTED.read_text(encoding="utf-8"))["version"]


def in_subsample(item: dict) -> bool:
    """The fixed subsample for the perturbation stage: every test item of claim and suggest, and the
    review items of one ad in four."""
    if item["split"] != "test" or item["family"] not in prompts.BINARY:
        return False
    return item["family"] != "review" or h("perturb:" + item["cluster"]) % 4 == 0


def req(item, version, **kw):
    effort = kw.pop("effort", llm.EFFORT)
    system, content, schema = prompts.request(item, version, **kw)
    return llm.params(system, content, schema, effort=effort)


def stage_dev(items, versions):
    out = {}
    for it in items:
        if it["split"] == "dev" and it["family"] in prompts.BINARY:
            for v in versions:
                out[f"dev|{it['id']}|{v}"] = req(it, v)
    return out


def stage_main(items, _):
    a = adopted()
    out = {}
    for it in items:
        if it["split"] != "test":
            continue
        if it["family"] in prompts.BINARY:
            for k in range(1, REPEATS + 1):
                out[f"main|{it['id']}|{a}|r{k}"] = req(it, a)
            if a != "v1":
                out[f"main|{it['id']}|v1|r1"] = req(it, "v1")
        elif it["family"] in FIXED:
            for k in range(1, REPEATS + 1):
                out[f"main|{it['id']}|fixed|r{k}"] = req(it, "fixed")
    return out


def stage_perturb(items, _):
    a = adopted()
    out = {}
    for it in items:
        if not in_subsample(it):
            continue
        out[f"pert|{it['id']}|r1"] = req(it, a, wording="r1")
        out[f"pert|{it['id']}|r2"] = req(it, a, wording="r2")
        out[f"pert|{it['id']}|swap"] = req(it, a, swap=True)
        out[f"pert|{it['id']}|verbose"] = req(it, a, cand=prompts.perturb_candidate(it, "verbose"))
        out[f"pert|{it['id']}|assertive"] = req(it, a, cand=prompts.perturb_candidate(it, "assertive"))
        out[f"pert|{it['id']}|low"] = req(it, a, effort="low")
    return out


# ------------------------------------------------------------------------------------------- pairs
PAIR_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "right": {"type": "string", "enum": ["A", "B"]}},
               "required": ["reason", "right"], "additionalProperties": False}
WRONG_ORDER = ("flip", "clause", "quote", "format")


def pairs(items) -> list[tuple[str, dict, dict]]:
    """(pair id, right item, wrong item) for the test split: review ads and suggestion pairs."""
    by_cluster = defaultdict(dict)
    for it in items:
        if it["split"] == "test" and it["family"] == "review":
            by_cluster[it["cluster"]][it["id"].rsplit("-", 1)[1]] = it
    out = []
    for c in sorted(by_cluster):
        d = by_cluster[c]
        wrong = next((d[w] for w in WRONG_ORDER if w in d), None)
        if "ok1" in d and wrong:
            out.append((f"rev-{c}", d["ok1"], wrong))
    sug = defaultdict(dict)
    for it in items:
        if it["split"] == "test" and it["family"] == "suggest":
            sug[it["meta"]["pair"]]["good" if it["truth"] == "pass" else "bad"] = it
    for p in sorted(sug):
        if len(sug[p]) == 2:
            out.append((p, sug[p]["good"], sug[p]["bad"]))
    return out


def pair_request(right: dict, wrong: dict, order: str, version: str):
    fam = right["family"]
    crit = "\n".join(f"- {q}" for _, q, _, _ in prompts.criteria(fam))
    plural = {"review": "ad reviews", "claim": "verdicts from a resume screen", "suggest": "suggestions to a seller about one selling point"}[fam]
    system = (f"You check {plural}. One such candidate is {prompts.WHAT[fam].split(': ', 1)[-1]}.\n{prompts.FAMILY_NOTE[fam]}\n"
              "Two candidates, A and B, are given for the same material. Exactly one of them is right by the questions below; the other is not. "
              "Say which one is right, after a one-sentence reason.\n" + crit)
    if version == "v4":
        system += "\n\n" + prompts.GUARDS
    if fam == "review":
        system += "\n\nPolicy library (" + right["material"]["jurisdiction"] + "):\n\n" + prompts.library_text(right["material"]["jurisdiction"])
    first, second = (right, wrong) if order == "AB" else (wrong, right)
    body = lambda it: prompts.candidate_text(fam, it["candidate"]).split("\n", 1)[1]  # noqa: E731  (without its heading line)
    text = "Candidate A:\n" + body(first) + "\n\nCandidate B:\n" + body(second)
    return llm.params(system, prompts.context_blocks(right) + [{"type": "text", "text": text}], PAIR_SCHEMA)


def stage_pair(items, _):
    a = adopted()
    out = {}
    for pid, right, wrong in pairs(items):
        for order in ("AB", "BA"):   # AB: the right candidate is shown first
            out[f"pair|{pid}|{order}"] = pair_request(right, wrong, order, a)
    return out


# ------------------------------------------------------------------------------------------- lists
def lists(items) -> dict[str, list[dict]]:
    """Per resume, its test verdicts in a fixed order (claim family)."""
    by = defaultdict(list)
    for it in items:
        if it["split"] == "test" and it["family"] == "claim":
            by[it["cluster"]].append(it)
    return {c: sorted(v, key=lambda it: h("list:" + it["id"])) for c, v in sorted(by.items()) if len(v) >= 3}


def list_request(group: list[dict], version: str):
    one = prompts.schema_binary("claim", version)
    props = {"n": {"type": "integer"}, **one["properties"]}
    schema = {"type": "object", "properties": {"results": {"type": "array", "items": {
        "type": "object", "properties": props, "required": list(props), "additionalProperties": False}}},
        "required": ["results"], "additionalProperties": False}
    system = prompts.system_binary("claim", version).replace(
        "You check one verdict from a resume screen:", "You check several verdicts from a resume screen about the same resume, numbered below. Each is of this kind:")
    system += "\n\nAnswer for every numbered verdict, in a list, giving its number as n."
    m = group[0]["material"]
    parts = [f"Job posting:\n\n{m['job']}\n\nResume:\n\n{m['resume']}"]
    for n, it in enumerate(group, 1):
        parts.append(f"Verdict {n}\nRequirement: {it['material']['requirement']}\n" + prompts.candidate_text("claim", it["candidate"]).split("\n", 1)[1])
    return llm.params(system, [{"type": "text", "text": "\n\n".join(parts)}], schema)


def stage_list(items, _):
    a = adopted()
    out = {}
    for c, group in lists(items).items():
        out[f"list|{c}|fwd"] = list_request(group, a)
        out[f"list|{c}|rev"] = list_request(list(reversed(group)), a)
    return out


STAGES = {"dev": stage_dev, "main": stage_main, "perturb": stage_perturb, "pair": stage_pair, "list": stage_list}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(STAGES))
    ap.add_argument("--versions", default=",".join(prompts.VERSIONS))
    ap.add_argument("--dry", action="store_true", help="count the requests, send nothing")
    ap.add_argument("--families", default="", help="only these families, comma-separated (a correction run)")
    ap.add_argument("--suffix", default="", help="store suffix of a correction run, e.g. c1: answers go to <stage>-c1.jsonl")
    a = ap.parse_args()
    items = load_all()
    if a.families:
        items = [i for i in items if i["family"] in a.families.split(",")]
    reqs = STAGES[a.stage](items, a.versions.split(","))
    print(f"{a.stage}: {len(reqs)} requests", dict(Counter(k.split("|")[-1] if a.stage != "main" else k.split("|")[2] for k in reqs)))
    if a.dry:
        return 0
    store = RAW / (f"{a.stage}-{a.suffix}.jsonl" if a.suffix else f"{a.stage}.jsonl")
    llm.run(reqs, store)
    print(llm.total_cost(store))
    return 0


if __name__ == "__main__":
    sys.exit(main())
