"""Builds the judging items from their sources. Deterministic: the same sources give the same files.

Every item is one thing for the judge to decide, with the answer it is scored against and where that
answer comes from (the `reference` field):

  constructed  the answer was fixed when the item was written, or the error was planted by a rule below
  regulator    the answer is a published decision of a regulator or court
  human        the answer is a human rating that ships with a public dataset

Families and sources (sibling folders by default, see SRC below):
  review     ad reviews (decision, clause, quotes) on the Grounded Review test ads, right ones from stored
             outputs and wrong ones planted here; text and image ads, Chinese and English
  claim      "meets the requirement" verdicts on synthetic resumes (Evidence Screening), right ones and
             planted misreadings, plus planted quote and figure errors
  suggest    listing-rewrite suggestions (Sellpoint Check calibration pairs: one that should pass, one
             that should fail, with the reason)
  regulator  ads described in UK ASA rulings and Chinese regulator/court cases (text not redistributed)
  jv         Judge's Verdict: RAG answers scored 0 / 0.5 / 1 by three annotators each (CC BY-SA 4.0)
  summeval   SummEval: news summaries rated 1-5 on four dimensions by three experts (MIT; articles not redistributed)
  mqm        WMT MQM Chinese-to-English: translations with professional error annotation (Apache-2.0)

Usage:  python eval/build_items.py            writes data/items/*.jsonl and private/items/*.jsonl
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from judgecal import rules  # noqa: E402

SIB = Path(os.environ.get("JC_SOURCES", ROOT.parent))
SRC = {
    "review": Path(os.environ.get("JC_SRC_REVIEW", SIB / "ad-review-agent")),
    "claim": Path(os.environ.get("JC_SRC_CLAIM", SIB / "evidence-screening-public")),
    "suggest": Path(os.environ.get("JC_SRC_SUGGEST", SIB / "sellpoint-check-public")),
    "hf": Path(os.environ.get("JC_DATA", ROOT / "private" / "downloads")),
}
PUB = ROOT / "data" / "items"
PRIV = ROOT / "private" / "items"
FLIPS = ROOT / "data" / "generated" / "review_flips.jsonl"


def h(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def write(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def split_of(cluster: str) -> str:
    """A quarter of the clusters is the development split used to choose the judge prompt."""
    return "dev" if h("split:" + cluster) % 4 == 0 else "test"


# ---------------------------------------------------------------------------------------------- review
def _review_sources():
    import yaml

    src = SRC["review"]
    items = {}
    for name in ("items_zh", "items_en", "items_hard_zh", "items_hard_en"):
        for it in yaml.safe_load((src / "testset" / f"{name}.yaml").read_text(encoding="utf-8")):
            it["lang"] = "zh" if it["id"].startswith("zh") else "en"
            items[it["id"]] = it
    # correction 2 (see the change log): labels the source added to six answer keys after its runs
    corr = src / "testset" / "key_corrections_2026-11-18.yaml"
    if corr.exists() and not os.environ.get("JC_REGISTERED_KEYS"):
        for c in yaml.safe_load(corr.read_text(encoding="utf-8")):
            items[c["id"]]["labels"] = list(items[c["id"]]["labels"]) + [dict(c["add"])]
    ocr = json.loads((src / "testset" / "ocr.json").read_text(encoding="utf-8"))
    rows = []
    for name in ("test-2026-11-13", "hard-2026-11-14", "dev-1", "dev-2"):
        for line in (src / "eval" / "results" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error") and r.get("output") and r["item"] in items:
                    rows.append(r)
    return items, ocr, rows


LABEL_SHAPES = {"bottle", "liquor", "wine", "oil", "beer", "pills", "tube", "jar", "candle", "tumbler", "teaware", "phone",
                "card", "powerbank", "book", "box", "tea", "blender", "bag", "jacket", "sofa", "bedding"}


def ad_text(item: dict) -> str:
    """All words of the ad (caption, then the lines drawn in the image): what ad quotes are checked against.
    Same rule as testset/load.py in Grounded Review."""
    lines = []
    if item["kind"] == "image":
        spec = item["image"]
        lines = list(spec["lines"]) + list(spec.get("small", []))
        if spec["layout"] in {"poster", "banner"} and spec.get("shape") in LABEL_SHAPES and spec.get("brand"):
            lines.append(spec["brand"])
    parts = [f"Caption: {item['copy']}"] if item["lang"] == "en" else [f"文案：{item['copy']}"]
    if lines:
        parts.append(("Words in the image:" if item["lang"] == "en" else "图片中的文字：") + "\n" + "\n".join(lines))
    return "\n".join(parts) + "\n"


def strictly_right(item: dict, out: dict) -> bool:
    """A stored review counts as a right candidate only if it matches the answer key in full:
    the decision, the set of violation categories, and a clause the key accepts for each category."""
    truth = "reject" if item["labels"] else "approve"
    if out["decision"] != truth:
        return False
    if truth == "approve":
        return not out["violations"]
    if {v["category"] for v in out["violations"]} != {l["cat"] for l in item["labels"]}:
        return False
    return all(any(v["clause_id"] in l["clauses"] for l in item["labels"] if l["cat"] == v["category"]) for v in out["violations"])


def alter_quote(quote: str, lang: str) -> str | None:
    """One small change that makes a quote no longer verbatim: a digit moved by one, else one letter or
    character dropped from the middle."""
    digits = [m.start() for m in re.finditer(r"\d", quote)]
    if digits:
        i = digits[len(digits) // 2]
        return quote[:i] + str((int(quote[i]) + 1) % 10) + quote[i + 1:]
    spots = [i for i, ch in enumerate(quote) if ch.isalpha()]
    if len(spots) < 3:
        return None
    i = spots[len(spots) // 2]
    return quote[:i] + quote[i + 1:]


def first_sentence(text: str) -> str:
    """A verbatim opening piece of a clause, long enough to be checked."""
    text = text.strip()
    m = re.search(r"[。；.;\n]", text[12:])
    cut = text[: 12 + m.start()] if m else text[:80]
    return cut.strip()


def build_review() -> list[dict]:
    items, ocr, rows = _review_sources()
    per = defaultdict(list)
    for r in rows:
        per[r["item"]].append(r)
    flips = {}
    if FLIPS.exists():
        for line in FLIPS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                f = json.loads(line)
                flips[f["ad"]] = f["review"]
    out, dropped = [], Counter()
    for aid in sorted(items):
        item = items[aid]
        jur = "CN" if item["lang"] == "zh" else "TikTok"
        material = {"jurisdiction": jur, "ad_text": ad_text(item), "caption": item["copy"],
                    "image": f"images/{aid}.png" if item["kind"] == "image" else None,
                    "ocr": ocr.get(aid, {}).get("text") if item["kind"] == "image" else None}
        truth_decision = "reject" if item["labels"] else "approve"

        def make(tag, cand, truth, dim, rule_checkable, note=""):
            return {"id": f"rev-{aid}-{tag}", "family": "review", "reference": "constructed", "lang": item["lang"],
                    "modality": item["kind"], "split": "dev" if item["split"] == "dev" else "test", "cluster": aid,
                    "dimension": dim, "rule_checkable": rule_checkable, "truth": truth, "material": material,
                    "candidate": cand, "public": True,
                    "meta": {"ad_split": item["split"], "answer": truth_decision, "trap": "trap" in item, "note": note}}

        # right candidates: stored reviews that match the answer key in full and pass the rule checks
        right = []
        for r in sorted(per[aid], key=lambda r: (r["arm"] != "oneshot", r.get("run", 0))):
            cand = {k: r["output"][k] for k in ("decision", "violations", "notes")}
            if strictly_right(item, cand) and not rules.review_problems(material, cand):
                if all(r["arm"] != x[0] for x in right):   # one per arm
                    right.append((r["arm"], cand))
        if not right:
            dropped["no stored review matches the answer key in full"] += 1
            continue
        for n, (arm, cand) in enumerate(right[:2], 1):
            out.append(make(f"ok{n}", cand, "pass", "correct", False, note=f"stored review, arm {arm}"))
        base = right[0][1]

        # planted: the opposite decision, argued (generated once, kept only if it passes the rule checks)
        if aid in flips:
            cand = flips[aid]
            if cand["decision"] != truth_decision and not rules.review_problems(material, cand):
                out.append(make("flip", cand, "fail", "decision", False, note="argued for the wrong decision"))
            else:
                dropped["generated wrong-decision review not usable"] += 1

        if truth_decision == "reject":
            # planted: a clause (and category) that has nothing to do with the ad; its quote is verbatim
            clauses = [c for c in rules.policy(jur)["clauses"] if c["kind"] == "rule" and c["category"] != "other"
                       and c["category"] not in {l["cat"] for l in item["labels"]}]
            pick = clauses[h("clause:" + aid) % len(clauses)]
            cand = copy.deepcopy(base)
            cand["violations"][0].update(category=pick["category"], clause_id=pick["id"], policy_quote=first_sentence(pick["text"]))
            if not rules.review_problems(material, cand):
                out.append(make("clause", cand, "fail", "clause", False, note=f"clause swapped to {pick['id']}"))
            else:
                dropped["swapped clause did not pass the rule checks"] += 1
            # planted: an ad quote that is no longer verbatim (rule-checkable)
            cand = copy.deepcopy(base)
            v = next((v for v in cand["violations"] if v["ad_quote"].strip()), None)
            new = alter_quote(v["ad_quote"], item["lang"]) if v else None
            if new:
                v["ad_quote"] = new
                if "ad_quote_not_found" in rules.review_problems(material, cand):
                    out.append(make("quote", cand, "fail", "quote", True, note="one digit or character of the ad quote changed"))
                else:
                    dropped["altered quote still found in the ad"] += 1
            # planted: a clause id that does not exist (rule-checkable), every third rejecting ad
            if h("format:" + aid) % 3 == 0:
                cand = copy.deepcopy(base)
                cand["violations"][0]["clause_id"] = "CN-AL-99" if jur == "CN" else "TT-POLICY-0"
                out.append(make("format", cand, "fail", "format", True, note="clause id that is not in the library"))
        elif h("format:" + aid) % 2 == 0:
            # planted: "reject" with no violation listed (rule-checkable), every second approving ad
            cand = copy.deepcopy(base)
            cand["decision"] = "reject"
            out.append(make("format", cand, "fail", "format", True, note="reject with no violation listed"))
    print("review:", len(out), dict(Counter((i["split"], i["dimension"]) for i in out)), "dropped:", dict(dropped))
    return out


# ---------------------------------------------------------------------------------------------- claim
def job_text(job: dict) -> str:
    if job["lang"] == "zh":
        head = [f"岗位：{job['title']}", f"公司：{job['company']}（{job['location']}）", job["summary"], "", "岗位要求（均为必备）："]
    else:
        head = [f"Job: {job['title']}", f"Company: {job['company']} ({job['location']})", job["summary"], "", "Requirements (all must-haves):"]
    return "\n".join(head + [f"{r['id']}. {r['text']}" for r in job["requirements"]])


def build_claim() -> list[dict]:
    src = SRC["claim"]
    jobs = {j["id"]: j for j in json.loads((src / "data" / "jobs.json").read_text(encoding="utf-8"))["jobs"]}
    inst = {i["id"]: i for i in json.loads((src / "data" / "v3" / "instances" / "index.json").read_text(encoding="utf-8"))["instances"]}
    resume = {k: (src / "data" / "v3" / "instances" / v["file"]).read_text(encoding="utf-8").strip() for k, v in inst.items()}
    base = json.loads((src / "eval" / "verify" / "items.json").read_text(encoding="utf-8"))["items"]
    out = []

    def make(iid, b, cand, truth, dim, rule_checkable, note=""):
        i = inst[b["resume"]]
        job = jobs[i["job"]]
        req = next(r for r in job["requirements"] if r["id"] == b["req"])
        return {"id": iid, "family": "claim", "reference": "constructed", "lang": i["lang"], "modality": "text",
                "split": split_of("claim:" + b["resume"]), "cluster": b["resume"], "dimension": dim,
                "rule_checkable": rule_checkable, "truth": truth,
                "material": {"job": job_text(job), "resume": resume[b["resume"]], "requirement": f"{req['id']}: {req['text']}"},
                "candidate": cand, "public": True, "meta": {"note": note, "trap": b.get("trap")}}

    rights = []
    for b in base:
        cand = {"verdict": "met", "resume_fact": b["resume_fact"], "quotes": b["quotes"], "reasoning": b["comparison"]}
        if b["kind"] == "right":
            it = make(f"clm-{b['id']}", b, cand, "pass", "correct", False)
            if rules.claim_problems(it["material"], cand):
                continue   # a right verdict the quote check does not pass is left out
            rights.append((b, cand))
        else:
            it = make(f"clm-{b['id']}", b, cand, "fail", "misreading", False, note="misreading of real resume text")
        out.append(it)

    # planted, rule-checkable: taken in a fixed order from the right verdicts, 20 of each kind
    order = sorted(rights, key=lambda x: h("plant:" + x[0]["id"]))
    anchors = defaultdict(list)
    for b, cand in rights:
        if cand["quotes"]:
            anchors[inst[b["resume"]]["lang"]].append((b["resume"], cand["quotes"][0]))
    made = Counter()
    for b, cand in order:
        lang = inst[b["resume"]]["lang"]
        kind = min(("figure", "quote", "foreign"), key=lambda k: made[k])
        new = copy.deepcopy(cand)
        if kind == "figure":
            m = re.search(r"\d+", new["resume_fact"])
            if not m:
                continue
            new["resume_fact"] = new["resume_fact"][: m.start()] + str(int(m.group()) + 1).zfill(len(m.group())) + new["resume_fact"][m.end():]
            note = "a figure in the resume fact moved by one"
        elif kind == "quote":
            q = alter_quote(new["quotes"][0], lang) if new["quotes"] else None
            if not q:
                continue
            new["quotes"][0] = q
            note = "one digit or character of the first quote changed"
        else:
            pool = [a for rid, a in anchors[lang] if rid != b["resume"] and a not in resume[b["resume"]]]
            if not new["quotes"] or not pool:
                continue
            new["quotes"][0] = pool[h("foreign:" + b["id"]) % len(pool)]
            note = "first quote replaced by a line from another resume"
        it = make(f"clm-{b['id']}-{kind}", b, new, "fail", kind, True, note=note)
        if not rules.claim_problems(it["material"], new):
            continue   # the change happened to stay consistent with the resume; not a planted error
        if made[kind] < 20:
            out.append(it)
            made[kind] += 1
        if all(made[k] >= 20 for k in ("figure", "quote", "foreign")):
            break
    print("claim:", len(out), dict(Counter((i["split"], i["dimension"]) for i in out)))
    return out


# ---------------------------------------------------------------------------------------------- suggest
SUGGEST_SETS = {"v1": "", "zh": "zh/", "mixed": "mixed/", "mixed2": "mixed2/", "voice": "voice/", "voice2": "voice2/"}


def _calibration(path: Path) -> list[dict]:
    """Reads the CALIBRATION array of a suggest_calibration.mjs file (plain data) with Node."""
    code = "import(process.argv[1]).then(m => process.stdout.write(JSON.stringify(m.CALIBRATION)))"
    r = subprocess.run(["node", "-e", code, path.as_uri()], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def build_suggest() -> list[dict]:
    src = SRC["suggest"] / "testset"
    out = []
    for name, sub in SUGGEST_SETS.items():
        cases = json.loads((src / sub / "cases.json").read_text(encoding="utf-8"))
        prods = {p["key"]: p for p in cases["products"]}
        for c in _calibration(src / sub / "suggest_calibration.mjs"):
            p = prods[c["key"]]
            claim = next(x for x in p["claims"] if x["claim_id"] == c["claim_id"])
            gold = next(x for x in p["gold"] if x["claim_id"] == c["claim_id"])
            rev = {"r_" + r["review_id"]: r for r in p["reviews"]}
            text = lambda ids: [f"{rev[i]['title']}. {rev[i]['text']}" if rev[i].get("title") else rev[i]["text"] for i in ids]  # noqa: E731
            lang = "zh" if re.search(r"[一-鿿]", claim["text"]) else "en"
            material = {"product": p["title"], "claim": claim["text"], "label": gold["label"],
                        "support": text(gold["support"]), "refute": text(gold["refute"]),
                        # correction 1 (see the change log): the listing as the source project's grader saw it
                        "listing_wording": claim.get("source_quote", ""), "listing": list(p.get("features", []))}
            cluster = f"{name}-{c['key']}"
            for which in ("good", "bad"):
                out.append({"id": f"sug-{name}-{c['key']}-{c['claim_id']}-{which}", "family": "suggest", "reference": "constructed",
                            "lang": lang, "modality": "text", "split": split_of("suggest:" + cluster), "cluster": cluster,
                            "dimension": "correct" if which == "good" else c["fail_reason"], "rule_checkable": False,
                            "truth": "pass" if which == "good" else "fail", "material": material, "candidate": c[which],
                            "public": True, "meta": {"set": name, "pair": f"sug-{name}-{c['key']}-{c['claim_id']}"}})
    print("suggest:", len(out), dict(Counter((i["split"], i["dimension"]) for i in out)))
    return out


# ---------------------------------------------------------------------------------------------- regulator
def build_regulator() -> list[dict]:
    import yaml

    out = []
    for lang, regime in (("en", "UK-ASA"), ("zh", "CN")):
        path = SRC["review"] / "testset" / f"items_real_{lang}.yaml"
        if not path.exists():
            continue
        for it in yaml.safe_load(path.read_text(encoding="utf-8")):
            s = it["source"]
            out.append({"id": f"reg-{it['id']}", "family": "regulator", "reference": "regulator", "lang": lang, "modality": "text",
                        "split": "test", "cluster": it["id"],
                        "dimension": "evidence_dependent" if s.get("evidence_dependent") else "on_the_face",
                        "rule_checkable": False, "truth": "fail" if it["labels"] else "pass",
                        "material": {"regime": regime, "ad": it["copy"]}, "candidate": None, "public": False,
                        "meta": {"decision": s["decision"], "date": str(s.get("date", "")), "url": s.get("ruling") or s.get("report"),
                                 "categories": sorted({l["cat"] for l in it["labels"]})}})
    print("regulator:", len(out), dict(Counter((i["lang"], i["truth"], i["dimension"]) for i in out)))
    return out


# ---------------------------------------------------------------------------------------------- human-rated
def build_jv() -> list[dict]:
    path = SRC["hf"] / "hf" / "nvidia__judges-verdict" / "annotations_train.json"
    out = []
    for r in json.loads(path.read_text(encoding="utf-8")):
        scores = [float(a["score"]) for a in r["annotations"]]
        out.append({"id": f"jv-{r['item_name']}", "family": "jv", "reference": "human", "lang": "en", "modality": "text",
                    "split": "test", "cluster": r["item_name"],
                    "dimension": "annotators_agree" if len(set(scores)) == 1 else "annotators_split",
                    "rule_checkable": False, "truth": sorted(scores)[1],
                    "material": {"question": r["question"], "reference": r["gt_answer"], "answer": r["gen_answer"]},
                    "candidate": None, "public": True, "meta": {"scores": scores, "dataset": r["dataset_name"]}})
    print("jv:", len(out), dict(Counter((i["dimension"], i["truth"]) for i in out)))
    return out


SUMMEVAL_DIMS = ("coherence", "consistency", "fluency", "relevance")


def build_summeval(n_articles: int = 30, per_article: int = 4) -> list[dict]:
    import pandas as pd

    text = {}
    for f in (SRC["hf"] / "hf" / "mteb__summeval" / "data").glob("*.parquet"):
        for _, r in pd.read_parquet(f).iterrows():
            text[r["id"]] = r["text"]
    by_article = defaultdict(list)
    with (SRC["hf"] / "summeval-orig" / "model_annotations.aligned.jsonl").open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_article[r["id"]].append(r)
    articles = sorted(by_article, key=lambda a: h("summeval:" + a))[:n_articles]
    out = []
    for aid in articles:
        rows = sorted(by_article[aid], key=lambda r: r["model_id"])
        start = h("start:" + aid) % len(rows)
        step = len(rows) // per_article
        for k in range(per_article):
            r = rows[(start + k * step) % len(rows)]
            for dim in SUMMEVAL_DIMS:
                experts = [a[dim] for a in r["expert_annotations"]]
                out.append({"id": f"se-{aid[-10:]}-{r['model_id']}-{dim}", "family": "summeval", "reference": "human", "lang": "en",
                            "modality": "text", "split": "test", "cluster": aid, "dimension": dim, "rule_checkable": False,
                            "truth": sum(experts) / len(experts),
                            "material": {"article": text[aid], "summary": r["decoded"]}, "candidate": None, "public": False,
                            "meta": {"article_id": aid, "model_id": r["model_id"], "experts": experts,
                                     "crowd": [a[dim] for a in r["turker_annotations"]]}})
    print("summeval:", len(out), dict(Counter(i["dimension"] for i in out)))
    return out


def mqm_class(score: float) -> str:
    return "none" if score > -0.05 else ("minor" if score > -4.95 else "major")


def build_mqm(per_class: int = 80) -> list[dict]:
    import pandas as pd

    df = pd.read_csv(SRC["hf"] / "hf" / "RicardoRei__wmt-mqm-human-evaluation" / "train.csv")
    df = df[(df.lp == "zh-en") & (df.year == 2022)].dropna(subset=["src", "mt"])
    df = df[(df.src.str.len() >= 12) & (df.src.str.len() <= 200)]
    df = df.drop_duplicates(subset=["src", "mt"])
    df["cls"] = df.score.map(mqm_class)
    df["key"] = [h(f"mqm:{s}|{m}") for s, m in zip(df.src, df.mt)]
    out = []
    domains = sorted(df.domain.unique())
    for cls in ("none", "minor", "major"):
        picked, seen_src = [], set()
        pools = {d: df[(df.cls == cls) & (df.domain == d)].sort_values("key") for d in domains}
        ptr = dict.fromkeys(domains, 0)
        while len(picked) < per_class and any(ptr[d] < len(pools[d]) for d in domains):
            for d in domains:   # round robin over domains, one translation per source sentence
                while ptr[d] < len(pools[d]):
                    r = pools[d].iloc[ptr[d]]
                    ptr[d] += 1
                    if r.src not in seen_src:
                        seen_src.add(r.src)
                        picked.append(r)
                        break
                if len(picked) >= per_class:
                    break
        for r in picked:
            out.append({"id": f"mqm-{r.key:012x}", "family": "mqm", "reference": "human", "lang": "zh-en", "modality": "text",
                        "split": "test", "cluster": f"{r.key:012x}", "dimension": r.domain, "rule_checkable": False, "truth": cls,
                        "material": {"source": r.src, "translation": r.mt}, "candidate": None, "public": True,
                        "meta": {"mqm_score": float(r.score), "system": r.system, "year": int(r.year), "annotators": int(r.annotators)}})
    print("mqm:", len(out), dict(Counter((i["truth"], i["dimension"]) for i in out)))
    return out


BUILDERS = {"review": (build_review, PUB), "claim": (build_claim, PUB), "suggest": (build_suggest, PUB),
            "regulator": (build_regulator, PRIV), "jv": (build_jv, PUB), "summeval": (build_summeval, PRIV), "mqm": (build_mqm, PUB)}


def main() -> int:
    only = sys.argv[1:] or list(BUILDERS)
    for name in only:
        fn, where = BUILDERS[name]
        write(where / f"{name}.jsonl", fn())
    return 0


if __name__ == "__main__":
    sys.exit(main())
