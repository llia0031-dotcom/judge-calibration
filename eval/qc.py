"""Quality-check agent for annotation records, and the records it is tested on.

The records are ad-review labels, the kind an annotation team delivers: for one ad, the decision and, for a
rejected ad, each violation as a category, a clause id and the words of the ad that break it. Each test ad
gives two records: its answer key (correct) and one copy with one planted error (wrong). The error types:

  decision        approve and reject swapped                                   (only a reader can tell)
  category        the violation filed under another category and clause        (only a reader can tell)
  span_semantic   the quoted words exist in the ad but are not what breaks it  (only a reader can tell)
  span_altered    the quoted words are no longer verbatim                      (a script can tell)
  unknown_clause  a clause id that is not in the library                       (a script can tell)

The agent gets one record and the ad, an index of the policy library (ids and titles, not the text) and two
tools: check_span (is this span verbatim in the ad?) and get_clause (the text of a clause). It must say
whether the record is correct and, if not, what is wrong. Each tool round of all open records goes out as one
batch. The script-only check (judgecal.rules) is the baseline.

Usage:  python eval/qc.py build      writes data/items/qc.jsonl (no model calls)
        python eval/qc.py run        runs the agent on the test records (batched tool rounds)
        python eval/qc.py pilot      runs the agent live on six development records (mechanics only)
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from judgecal import llm, prompts, rules  # noqa: E402
from judgecal.items import h  # noqa: E402

OUT = ROOT / "data" / "items" / "qc.jsonl"
RAW = ROOT / "eval" / "results" / "raw"
MAX_ROUNDS = 5
ERROR_TYPES = ("decision", "category", "span_semantic", "span_altered", "unknown_clause")
RULE_CHECKABLE = {"span_altered", "unknown_clause"}


# ------------------------------------------------------------------------------------------- records
def record_of(item: dict) -> dict:
    """The answer key of a Grounded Review ad as an annotation record."""
    labels = []
    for l in item["labels"]:
        lab = {"category": l["cat"], "clause_id": l["clauses"][0], "span": l.get("span", "")}
        if not lab["span"]:
            lab["visual"] = l.get("visual") or l.get("absence") or ""
        labels.append(lab)
    return {"decision": "reject" if labels else "approve", "labels": labels}


def as_review(rec: dict) -> dict:
    """A record in the shape the rule checks read."""
    return {"decision": rec["decision"],
            "violations": [{"category": l["category"], "clause_id": l["clause_id"], "ad_quote": l.get("span", ""),
                            "visual_evidence": l.get("visual", "")} for l in rec["labels"]]}


def chunks(text: str, lang: str) -> list[str]:
    body = re.sub(r"^(Caption|文案)：?:?\s*", "", text, flags=re.M).replace("Words in the image:", "\n").replace("图片中的文字：", "\n")
    parts = [p.strip(" \"'“”「」") for p in re.split(r"[\n。，；！？,.;!?：:]", body)]
    least = 4 if lang == "zh" else 8
    return [p for p in parts if len(p) >= least]


def plant(item: dict, material: dict, rec: dict, jur: str) -> tuple[str, dict] | None:
    aid = item["id"]
    wrong = copy.deepcopy(rec)
    lib = [c for c in rules.policy(jur)["clauses"] if c["kind"] == "rule" and c["category"] != "other"]
    if rec["decision"] == "approve":
        cat = None
        if item.get("basis"):
            cats = {c["id"]: c["category"] for c in rules.policy(jur)["clauses"]}
            cat = next((cats[b] for b in item["basis"] if cats.get(b) not in (None, "other")), None)
        pool = [c for c in lib if c["category"] == cat] or lib
        clause = pool[h("qc-clause:" + aid) % len(pool)]
        span = (chunks(material["ad_text"], item["lang"]) or [item["copy"]])[0]
        wrong = {"decision": "reject", "labels": [{"category": clause["category"], "clause_id": clause["id"], "span": span}]}
        return "decision", wrong
    has_span = [i for i, l in enumerate(rec["labels"]) if l["span"]]
    roll = h("qc-type:" + aid) % 100
    kind = ("decision" if roll < 30 else "category" if roll < 55 else "span_semantic" if roll < 70 else
            "span_altered" if roll < 85 else "unknown_clause")
    if kind in ("span_semantic", "span_altered") and not has_span:
        kind = "category"
    if kind == "decision":
        return kind, {"decision": "approve", "labels": []}
    first = has_span[0] if has_span else 0
    if kind == "category":
        gold = {l["category"] for l in rec["labels"]}
        pool = [c for c in lib if c["category"] not in gold]
        clause = pool[h("qc-cat:" + aid) % len(pool)]
        wrong["labels"][0].update(category=clause["category"], clause_id=clause["id"])
        return kind, wrong
    if kind == "unknown_clause":
        wrong["labels"][0]["clause_id"] = "CN-AL-99" if jur == "CN" else "TT-POLICY-0"
        return kind, wrong
    span = rec["labels"][first]["span"]
    if kind == "span_altered":
        from build_items import alter_quote

        new = alter_quote(span, item["lang"])
        if not new or rules.found(material["ad_text"], new):
            return None
        wrong["labels"][first]["span"] = new
        return kind, wrong
    gold_spans = [l["span"] for l in rec["labels"] if l["span"]]
    pool = [c for c in chunks(material["ad_text"], item["lang"])
            if not any(c in s or s in c for s in gold_spans) and rules.found(material["ad_text"], c)]
    if not pool:
        return None
    wrong["labels"][first]["span"] = pool[h("qc-span:" + aid) % len(pool)]
    return kind, wrong


def build() -> int:
    import build_items as B

    items, ocr, _ = B._review_sources()
    out, skipped = [], Counter()
    for aid in sorted(items):
        it = items[aid]
        jur = "CN" if it["lang"] == "zh" else "TikTok"
        material = {"jurisdiction": jur, "ad_text": B.ad_text(it), "caption": it["copy"],
                    "image": f"images/{aid}.png" if it["kind"] == "image" else None}
        rec = record_of(it)
        if rules.review_problems(material, as_review(rec)):
            skipped["answer key does not pass the rule checks"] += 1
            continue
        split = "dev" if it["split"] == "dev" else "test"
        base = {"family": "qc", "reference": "constructed", "lang": it["lang"], "modality": it["kind"], "split": split,
                "cluster": aid, "material": material, "public": True}
        out.append({**base, "id": f"qc-{aid}-key", "truth": "pass", "dimension": "correct", "rule_checkable": False,
                    "candidate": rec, "meta": {"answer": rec["decision"]}})
        p = plant(it, material, rec, jur)
        if p is None:
            skipped["no planted error possible"] += 1
            continue
        kind, wrong = p
        caught = bool(rules.review_problems(material, as_review(wrong)))
        if caught != (kind in RULE_CHECKABLE):
            skipped[f"{kind}: rule check result not as intended"] += 1
            continue
        out.append({**base, "id": f"qc-{aid}-err", "truth": "fail", "dimension": kind, "rule_checkable": kind in RULE_CHECKABLE,
                    "candidate": wrong, "meta": {"answer": rec["decision"]}})
    B.write(OUT, out)
    print("qc records:", len(out), dict(Counter((r["split"], r["dimension"]) for r in out)), "skipped:", dict(skipped))
    return 0


# ------------------------------------------------------------------------------------------- the agent
TOOLS = [
    {"name": "check_span", "description": "Checks whether a span of text appears word for word in the ad (its caption and the words in its image). Returns found or not found.",
     "input_schema": {"type": "object", "properties": {"span": {"type": "string"}}, "required": ["span"], "additionalProperties": False}},
    {"name": "get_clause", "description": "Returns the title, kind (rule or guidance) and full text of one clause of the policy library, or says that no clause has this id.",
     "input_schema": {"type": "object", "properties": {"clause_id": {"type": "string"}}, "required": ["clause_id"], "additionalProperties": False}},
]
VERDICT = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["correct", "wrong"]},
    "problem": {"type": "string", "enum": ["none", "decision", "category_or_clause", "span", "format"]},
    "reason": {"type": "string"}, "confidence": {"type": "string", "enum": ["sure", "unsure"]}},
    "required": ["verdict", "problem", "reason", "confidence"], "additionalProperties": False}

SYSTEM = """You quality-check annotation records before a batch is accepted. Each record labels one ad: the decision (approve or reject) and, for a rejected ad, every violation as a category, the id of the clause broken, and the span: the exact words of the ad that break it (or, when the problem is only in the picture or is something the ad leaves out, a short description instead of a span).

A record is correct only if all of these hold:
- the decision is right: reject if the ad breaks at least one clause marked "rule", approve if it breaks none ("guidance" clauses say when a rule does not apply);
- every violation is real, under a fitting category, citing a clause that the ad does break;
- every span is copied word for word from the ad and is the part of the ad that breaks the clause;
- the record is well formed: a reject lists at least one violation, an approve lists none, and every clause id exists.

Use the tools before you decide: check every span with check_span, and read the text of every cited clause with get_clause (and of any other clause you rely on). Then give your verdict: "correct" or "wrong", the main problem (none, decision, category_or_clause, span or format), a one-sentence reason, and whether you are sure or unsure.

Categories:
{categories}

Policy library index ({jurisdiction}); read the text of a clause with get_clause:
{index}"""


def system_for(jur: str) -> str:
    pol = rules.policy(jur)
    cats = "\n".join(f"- {k}: {v['en']}" for k, v in pol["categories"].items())
    index = "\n".join(f"- {c['id']} ({c['kind']}): {c['title']}" for c in pol["clauses"])
    return SYSTEM.format(categories=cats, jurisdiction=jur, index=index)


def run_tool(item: dict, name: str, args: dict) -> tuple[str, bool]:
    jur = item["material"]["jurisdiction"]
    if name == "check_span":
        span = str(args.get("span", ""))
        return ("found word for word in the ad" if rules.found(item["material"]["ad_text"], span) else "not found in the ad"), False
    if name == "get_clause":
        c = {c["id"]: c for c in rules.policy(jur)["clauses"]}.get(str(args.get("clause_id", "")).strip())
        if c is None:
            return "no clause with this id in the library", False
        return f"[{c['id']}] {c['title']} ({c['kind']})\n{c.get('text', '(text not available in this copy)')}", False
    return f"unknown tool {name}", True


def first_message(item: dict) -> list[dict]:
    rec = "Record to check:\n" + json.dumps(item["candidate"], ensure_ascii=False, indent=1)
    return prompts._ad_blocks(item["material"]) + [{"type": "text", "text": rec}]


def agent_run(records: list[dict], stage: str, batch: bool = True, log=print) -> dict[str, dict]:
    """Runs the agent on every record; each round of tool calls of all open records is one batch.
    Returns, per record id, the final verdict (or an error), the tool calls and the usage."""
    store = RAW / f"{stage}.jsonl"
    convo = {r["id"]: [{"role": "user", "content": first_message(r)}] for r in records}
    calls = {r["id"]: [] for r in records}
    final, usage = {}, {r["id"]: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0} for r in records}
    by_id = {r["id"]: r for r in records}
    for rnd in range(1, MAX_ROUNDS + 1):
        open_ids = [i for i in convo if i not in final]
        if not open_ids:
            break
        reqs = {}
        for i in open_ids:
            p = llm.params(system_for(by_id[i]["material"]["jurisdiction"]), None, VERDICT)
            p["messages"] = convo[i]
            p["tools"] = TOOLS
            if rnd == MAX_ROUNDS:
                p["tool_choice"] = {"type": "none"}
            reqs[f"{stage}|{i}|t{rnd}"] = p
        res = llm.run(reqs, store, log=log, batch=batch)
        for i in open_ids:
            r = res.get(f"{stage}|{i}|t{rnd}")
            if r is None:
                final[i] = {"output": None, "error": "no answer"}
                continue
            u = usage[i]
            u["calls"] += 1
            u["input_tokens"] += r["usage"]["input_tokens"]
            u["output_tokens"] += r["usage"]["output_tokens"]
            u["cost_usd"] += r["cost_usd"]
            if r.get("stop_reason") == "tool_use":
                content = r["content"]
                convo[i].append({"role": "assistant", "content": content})
                results = []
                for b in content:
                    if b.get("type") == "tool_use":
                        text, err = run_tool(by_id[i], b["name"], b.get("input") or {})
                        calls[i].append({"name": b["name"], "input": b.get("input"), "output": text})
                        results.append({"type": "tool_result", "tool_use_id": b["id"], "content": text, "is_error": err})
                convo[i].append({"role": "user", "content": results})
            else:
                final[i] = {"output": r["output"], "error": r.get("error")}
    out = {}
    for i in convo:
        f = final.get(i, {"output": None, "error": "no final answer within the round limit"})
        out[i] = {**f, "tool_calls": calls[i], "usage": usage[i]}
    return out


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        return build()
    recs = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    if cmd == "pilot":
        pick = [r for r in recs if r["split"] == "dev"]
        pick = [r for r in pick if r["truth"] == "pass"][:2] + [r for r in pick if r["truth"] == "fail"][:4]
        res = agent_run(pick, "qc-pilot", batch=False)
        for r in pick:
            o = res[r["id"]]
            print(r["id"], r["truth"], r["dimension"], "->", json.dumps(o["output"], ensure_ascii=False)[:200], "| tools:",
                  [c["name"] for c in o["tool_calls"]], "| $", round(o["usage"]["cost_usd"], 5))
        return 0
    if cmd == "run":
        test = [r for r in recs if r["split"] == "test"]
        res = agent_run(test, "qc")
        path = ROOT / "eval" / "results" / "qc-agent.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in test:
                f.write(json.dumps({"id": r["id"], **res[r["id"]]}, ensure_ascii=False) + "\n")
        print("qc agent:", len(res), "records;", sum(1 for v in res.values() if v["output"]), "answered;",
              round(sum(v["usage"]["cost_usd"] for v in res.values()), 4), "USD")
        return 0
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    sys.exit(main())
