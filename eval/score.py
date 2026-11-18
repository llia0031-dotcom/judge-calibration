"""Scores everything from the stored answers. No model calls.

  python eval/score.py adopt     apply the adoption rule to the dev answers; writes eval/adopted.json
  python eval/score.py           all measures; writes eval/results/summary.json and eval/results/RESULTS.md

Every number in the report comes from summary.json; RESULTS.md is the same numbers as tables.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from judgecal import llm, prompts, rules, stats  # noqa: E402
from judgecal.items import h, load_all  # noqa: E402

RAW = ROOT / "eval" / "results" / "raw"
OUT = ROOT / "eval" / "results"
ADOPTED = ROOT / "eval" / "adopted.json"
RULE_DIMS = {"review": {"quote", "format"}, "claim": {"figure", "quote", "foreign"}, "qc": {"span_altered", "unknown_clause"}}
MQM_ORDER = {"none": 0, "minor": 1, "major": 2}


REGISTERED = "--as-registered" in sys.argv   # score the answers as registered, without the correction runs
CORRECTIONS = ("c1",)


def store(name: str) -> dict[str, dict]:
    """The stored answers of a stage. Unless REGISTERED, answers of a correction run (<stage>-c1.jsonl) replace
    the registered answers with the same key (see the change log of PREREGISTRATION.md)."""
    out = llm.load_store(RAW / f"{name}.jsonl")
    if not REGISTERED:
        for c in CORRECTIONS:
            out.update(llm.load_store(RAW / f"{name}-{c}.jsonl"))
    return out


def r4(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 6)


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return r4(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def mean_cost(recs) -> float:
    recs = [r for r in recs if r.get("usage")]
    return sum(r["cost_usd"] for r in recs) / len(recs) if recs else float("nan")


def recall_pair(rows):
    """rows: (truth, verdict). Pass recall, fail recall, balanced accuracy."""
    p = [v for t, v in rows if t == "pass"]
    f = [v for t, v in rows if t == "fail"]
    pr = stats.rate(sum(1 for v in p if v == "pass"), len(p))
    fr = stats.rate(sum(1 for v in f if v == "fail"), len(f))
    return {"pass_recall": pr, "fail_recall": fr, "ba": (pr["rate"] + fr["rate"]) / 2}


# ------------------------------------------------------------------------------------------- adoption (dev)
def dev_table(items):
    dev = store("dev")
    by_id = {i["id"]: i for i in items}
    versions = sorted({k.split("|")[2] for k in dev})
    out = {}
    for v in versions:
        fam_rows, recs = defaultdict(list), []
        for k, r in dev.items():
            _, iid, ver = k.split("|")
            if ver != v:
                continue
            it = by_id[iid]
            fam_rows[it["family"]].append((it["truth"], prompts.verdict_of(it, v, r["output"])))
            recs.append(r)
        fams = {f: recall_pair(rows) for f, rows in sorted(fam_rows.items())}
        n_expected = sum(1 for i in items if i["split"] == "dev" and i["family"] in prompts.BINARY)
        out[v] = {"families": fams, "score": statistics.mean(x["ba"] for x in fams.values()), "cost_per_call": mean_cost(recs),
                  "answered": len(recs), "expected": n_expected}
    return out


def adopt(items) -> dict:
    table = dev_table(items)
    current, steps = "v1", []
    for v in [x for x in table if x != "v1"]:
        a, c = table[v], table[current]
        checks = {
            "score_up_0.02": a["score"] >= c["score"] + 0.02,
            "no_fail_recall_drop_0.05": all(a["families"][f]["fail_recall"]["rate"] >= c["families"][f]["fail_recall"]["rate"] - 0.05 for f in a["families"]),
            "no_pass_recall_drop_0.05": all(a["families"][f]["pass_recall"]["rate"] >= c["families"][f]["pass_recall"]["rate"] - 0.05 for f in a["families"]),
            "cost_at_most_1.5x": a["cost_per_call"] <= 1.5 * c["cost_per_call"],
        }
        ok = all(checks.values())
        steps.append({"candidate": v, "against": current, "checks": checks, "adopted": ok})
        if ok:
            current = v
    return {"version": current, "steps": steps, "table": table}


# ------------------------------------------------------------------------------------------- helpers for main
def majority(vals):
    c = Counter(vals)
    top, n = c.most_common(1)[0]
    if n > len(vals) / 2:
        return top
    return sorted(vals, key=lambda x: (MQM_ORDER.get(x, x) if isinstance(x, str) else x))[len(vals) // 2]


def judged(items, st, version, repeats=3, prefix="main"):
    """item id -> list of verdicts (in repeat order) for items with all judgments answered."""
    out = {}
    for it in items:
        vs = []
        for k in range(1, repeats + 1):
            r = st.get(f"{prefix}|{it['id']}|{version}|r{k}")
            if r is None or r.get("output") is None:
                break
            vs.append(prompts.verdict_of(it, version if version != "fixed" else "v2", r["output"]))
        if len(vs) == repeats:
            out[it["id"]] = vs
    return out


def confidence(st, iid, version, k):
    r = st.get(f"main|{iid}|{version}|r{k}")
    return (r or {}).get("output", {}).get("confidence") if r and r.get("output") else None


def block(rows, clusters, positive="fail"):
    truth = [t for t, _ in rows]
    verd = [v for _, v in rows]
    b = stats.agreement_block(truth, verd, positive=positive, clusters=clusters)
    b.update(recall_pair(rows))
    return b


def binary_section(items, st, a):
    test = [i for i in items if i["split"] == "test" and i["family"] in prompts.BINARY]
    J = judged(test, st, a)
    J1 = judged(test, st, "v1", repeats=1)
    res = {"answered": len(J), "expected": len(test), "families": {}}
    for fam in prompts.BINARY:
        its = [i for i in test if i["family"] == fam and i["id"] in J]
        rows = [(i["truth"], majority(J[i["id"]])) for i in its]
        cl = [i["cluster"] for i in its]
        f = {"overall": block(rows, cl)}
        for key in ("dimension", "lang", "modality"):
            groups = defaultdict(list)
            for i in its:
                groups[i[key]].append(i)
            f["by_" + key] = {}
            for g, gi in sorted(groups.items()):
                gr = [(i["truth"], majority(J[i["id"]])) for i in gi]
                ok = sum(1 for t, v in gr if t == v)
                f["by_" + key][g] = {"n": len(gr), "right": stats.rate(ok, len(gr)), **({} if key == "dimension" else recall_pair(gr))}
        # stability
        same = sum(1 for i in its if len(set(J[i["id"]])) == 1)
        f["stability"] = {"all_three_same": stats.rate(same, len(its)), "fleiss": stats.fleiss([J[i["id"]] for i in its])}
        f["stability_by_dimension"] = {}
        for d in sorted({i["dimension"] for i in its}):
            di = [i for i in its if i["dimension"] == d]
            f["stability_by_dimension"][d] = stats.rate(sum(1 for i in di if len(set(J[i["id"]])) == 1), len(di))
        # v1 baseline, one judgment, against the adopted version's first judgment
        its1 = [i for i in its if i["id"] in J1]
        f["v1_single"] = recall_pair([(i["truth"], J1[i["id"]][0]) for i in its1])
        f["adopted_single"] = recall_pair([(i["truth"], J[i["id"]][0]) for i in its1])
        f["v1_single"]["n"] = len(its1)
        # rule layer recall on the judge's own: judge alone on rule-checkable dims
        if fam in RULE_DIMS:
            rd = [i for i in its if i["dimension"] in RULE_DIMS[fam]]
            f["judge_on_rule_checkable"] = stats.rate(sum(1 for i in rd if majority(J[i["id"]]) == "fail"), len(rd))
        res["families"][fam] = f
    # pooled
    its = [i for i in test if i["id"] in J]
    rows = [(i["truth"], majority(J[i["id"]])) for i in its]
    res["pooled"] = block(rows, [i["cluster"] for i in its])
    rd = [i for i in its if i["dimension"] in RULE_DIMS.get(i["family"], set())]
    res["judge_on_rule_checkable"] = stats.rate(sum(1 for i in rd if majority(J[i["id"]]) == "fail"), len(rd))
    res["stability_all_three_same"] = stats.rate(sum(1 for i in its if len(set(J[i["id"]])) == 1), len(its))
    res["cost_per_call"] = {fam: mean_cost([st[k] for k in st if k.startswith("main|") and f"|{a}|" in k and k.split("|")[1].startswith(
        {"review": "rev-", "claim": "clm-", "suggest": "sug-"}[fam])]) for fam in prompts.BINARY}
    return res, J


def regulator_section(items, st):
    its = [i for i in items if i["family"] == "regulator"]
    J = judged(its, st, "fixed")
    its = [i for i in its if i["id"] in J]
    rows = [(i["truth"], majority(J[i["id"]])) for i in its]
    res = {"overall": block(rows, [i["cluster"] for i in its]), "expected": len([i for i in items if i["family"] == "regulator"])}
    for key in ("lang", "dimension"):
        res["by_" + key] = {}
        for g in sorted({i[key] for i in its}):
            gi = [i for i in its if i[key] == g]
            gr = [(i["truth"], majority(J[i["id"]])) for i in gi]
            res["by_" + key][g] = {"n": len(gr), "agreement": stats.rate(sum(1 for t, v in gr if t == v), len(gr)), **recall_pair(gr)}
    res["stability"] = stats.rate(sum(1 for i in its if len(set(J[i["id"]])) == 1), len(its))
    res["unsure_share"] = stats.rate(sum(1 for i in its if confidence(st, i["id"], "fixed", 1) == "unsure"), len(its))
    return res, J


def jv_section(items, st):
    its = [i for i in items if i["family"] == "jv"]
    J = judged(its, st, "fixed")
    its = [i for i in its if i["id"] in J]
    lv = {0.0: 0, 0.5: 1, 1.0: 2}
    judge = [lv[majority(J[i["id"]])] for i in its]
    truth = [lv[i["truth"]] for i in its]
    ann = [[lv[s] for s in i["meta"]["scores"]] for i in its]   # annotator order as published
    cl = [i["cluster"] for i in its]
    res = {"n": len(its), "exact": stats.rate(sum(1 for a, b in zip(judge, truth) if a == b), len(its)),
           "weighted_kappa": stats.kappa_ci(truth, judge, weights="quadratic", clusters=cl)}
    # pairwise among annotators (positions 1-3 as listed per item) and judge against each
    pairs = {}
    for a, b in ((0, 1), (0, 2), (1, 2)):
        x, y = [r[a] for r in ann], [r[b] for r in ann]
        pairs[f"A{a + 1}-A{b + 1}"] = {"exact": sum(1 for p, q in zip(x, y) if p == q) / len(x), "wkappa": stats.cohen_kappa(x, y, weights="quadratic")}
    jvs = {}
    for a in range(3):
        x = [r[a] for r in ann]
        jvs[f"judge-A{a + 1}"] = {"exact": sum(1 for p, q in zip(x, judge) if p == q) / len(x), "wkappa": stats.cohen_kappa(x, judge, weights="quadratic")}
    res["human_pairs"] = pairs
    res["judge_vs_each"] = jvs
    res["human_range_exact"] = [min(p["exact"] for p in pairs.values()), max(p["exact"] for p in pairs.values())]
    res["human_range_wkappa"] = [min(p["wkappa"] for p in pairs.values()), max(p["wkappa"] for p in pairs.values())]
    res["judge_mean_exact"] = statistics.mean(v["exact"] for v in jvs.values())
    res["judge_mean_wkappa"] = statistics.mean(v["wkappa"] for v in jvs.values())
    res["human_mean_exact"] = statistics.mean(p["exact"] for p in pairs.values())
    res["human_mean_wkappa"] = statistics.mean(p["wkappa"] for p in pairs.values())
    res["by_dimension"] = {}
    for d in sorted({i["dimension"] for i in its}):
        idx = [k for k, i in enumerate(its) if i["dimension"] == d]
        res["by_dimension"][d] = {"n": len(idx), "exact": stats.rate(sum(1 for k in idx if judge[k] == truth[k]), len(idx)),
                                  "weighted_kappa": stats.cohen_kappa([truth[k] for k in idx], [judge[k] for k in idx], weights="quadratic")}
    res["confusion"] = {f"truth {t} judge {j}": n for (t, j), n in sorted(Counter(zip(truth, judge)).items())}
    res["stability"] = stats.rate(sum(1 for i in its if len(set(J[i["id"]])) == 1), len(its))
    return res, J


def summeval_section(items, st):
    its = [i for i in items if i["family"] == "summeval"]
    J = judged(its, st, "fixed")
    res = {}
    for d in prompts.SUMMEVAL_DEF:
        di = [i for i in its if i["dimension"] == d and i["id"] in J]
        jm = np.array([statistics.mean(J[i["id"]]) for i in di])
        em = np.array([i["truth"] for i in di])
        cl = [i["cluster"] for i in di]
        sp = stats.spearman(jm, em)
        lo, hi = stats.cluster_bootstrap(lambda idx: stats.spearman(jm[idx], em[idx]), cl)
        ex = np.array([i["meta"]["experts"] for i in di], dtype=float)
        ceil = statistics.mean(stats.spearman(ex[:, e], ex[:, [k for k in range(3) if k != e]].mean(axis=1)) for e in range(3))
        crowd = np.array([statistics.mean(i["meta"]["crowd"]) for i in di])
        res[d] = {"n": len(di), "spearman": sp, "spearman_lo": lo, "spearman_hi": hi, "kendall": stats.kendall(jm, em),
                  "expert_ceiling_spearman": ceil, "crowd_vs_expert_spearman": stats.spearman(crowd, em),
                  "judge_mean": float(jm.mean()), "expert_mean": float(em.mean()),
                  "stable_within_1": stats.rate(sum(1 for i in di if max(J[i["id"]]) - min(J[i["id"]]) <= 1), len(di)),
                  "all_three_same": stats.rate(sum(1 for i in di if len(set(J[i["id"]])) == 1), len(di))}
    return res, J


def mqm_section(items, st):
    its = [i for i in items if i["family"] == "mqm"]
    J = judged(its, st, "fixed")
    its = [i for i in its if i["id"] in J]
    t = [MQM_ORDER[i["truth"]] for i in its]
    j = [MQM_ORDER[majority(J[i["id"]])] for i in its]
    cl = [i["cluster"] for i in its]
    res = {"n": len(its), "exact": stats.rate(sum(1 for a, b in zip(t, j) if a == b), len(its)),
           "weighted_kappa": stats.kappa_ci(t, j, weights="quadratic", clusters=cl),
           "recall": {c: stats.rate(sum(1 for a, b in zip(t, j) if a == v and b == v), sum(1 for a in t if a == v)) for c, v in MQM_ORDER.items()},
           "any_error_recall": stats.rate(sum(1 for a, b in zip(t, j) if a > 0 and b > 0), sum(1 for a in t if a > 0)),
           "none_kept": stats.rate(sum(1 for a, b in zip(t, j) if a == 0 and b == 0), sum(1 for a in t if a == 0)),
           "confusion": {f"truth {a} judge {b}": n for (a, b), n in sorted(Counter(zip(t, j)).items())},
           "stability": stats.rate(sum(1 for i in its if len(set(J[i["id"]])) == 1), len(its)), "by_domain": {}}
    for d in sorted({i["dimension"] for i in its}):
        idx = [k for k, i in enumerate(its) if i["dimension"] == d]
        res["by_domain"][d] = {"n": len(idx), "exact": stats.rate(sum(1 for k in idx if t[k] == j[k]), len(idx)),
                               "weighted_kappa": stats.cohen_kappa([t[k] for k in idx], [j[k] for k in idx], weights="quadratic")}
    return res, J


# ------------------------------------------------------------------------------------------- 7.5 grouping
def grouping(binr, reg, jv, se, mq):
    rows = []

    def put(family, dim, metric_name, metric, stable, rule=False, thr=0.85):
        if rule:
            group = "rule-checkable"
        elif metric is not None and stable is not None and metric >= thr and stable >= 0.90:
            group = "judge-reliable"
        else:
            group = "needs people"
        rows.append({"family": family, "dimension": dim, "metric": metric_name, "value": metric, "stable": stable, "group": group})

    for fam, f in binr["families"].items():
        for d, x in f["by_dimension"].items():
            put(fam, d, "pass recall" if d == "correct" else "errors caught", x["right"]["rate"], f["stability_by_dimension"][d]["rate"],
                rule=d in RULE_DIMS.get(fam, set()))
    for d, x in reg["by_dimension"].items():
        put("regulator", d, "agreement", x["agreement"]["rate"], reg["stability"]["rate"])
    for d, x in jv["by_dimension"].items():
        put("jv", d, "weighted kappa", x["weighted_kappa"], jv["stability"]["rate"], thr=0.6)
    for d, x in se.items():
        put("summeval", d, "Spearman", x["spearman"], x["stable_within_1"]["rate"], thr=0.6)
    for d, x in mq["by_domain"].items():
        put("mqm", d, "weighted kappa", x["weighted_kappa"], mq["stability"]["rate"], thr=0.6)
    return rows


# ------------------------------------------------------------------------------------------- 7.6 combination
def combination(items, st, a, J):
    test = [i for i in items if i["split"] == "test" and i["family"] in prompts.BINARY and i["id"] in J]
    cost = {i["id"]: [st[f"main|{i['id']}|{a}|r{k}"]["cost_usd"] for k in (1, 2)] for i in test}
    out = {}
    for arm in ("A", "B", "C"):
        auto_fail = auto_pass = queue = missed = false_alarm = calls = 0
        usd = 0.0
        for i in test:
            truth = i["truth"]
            if arm != "A" and rules.problems(i):
                auto_fail += 1
                false_alarm += truth == "pass"
                continue
            v1, v2 = J[i["id"]][0], J[i["id"]][1]
            c1, c2 = confidence(st, i["id"], a, 1), confidence(st, i["id"], a, 2)
            calls += 1 if arm != "C" else 2
            usd += cost[i["id"]][0] + (cost[i["id"]][1] if arm == "C" else 0)
            if arm == "A":
                to_queue = False
            elif arm == "B":
                to_queue = c1 == "unsure"
            else:
                to_queue = c1 == "unsure" or c2 == "unsure" or v1 != v2
            if to_queue:
                queue += 1
                continue
            if v1 == "pass":
                auto_pass += 1
                missed += truth == "fail"
            else:
                auto_fail += 1
                false_alarm += truth == "pass"
        n = len(test)
        n_fail = sum(1 for i in test if i["truth"] == "fail")
        out[arm] = {"n": n, "wrong_candidates": n_fail, "coverage": stats.rate(n - queue, n), "queue": stats.rate(queue, n),
                    "missed": stats.rate(missed, n_fail), "false_alarms": stats.rate(false_alarm, n - n_fail),
                    "judge_calls": calls, "cost_usd": usd, "cost_per_1000_items": usd / n * 1000}
    # per family for B
    out["B_by_family"] = {}
    for fam in prompts.BINARY:
        ft = [i for i in test if i["family"] == fam]
        miss = q = 0
        for i in ft:
            if rules.problems(i):
                continue
            if confidence(st, i["id"], a, 1) == "unsure":
                q += 1
            elif J[i["id"]][0] == "pass" and i["truth"] == "fail":
                miss += 1
        nf = sum(1 for i in ft if i["truth"] == "fail")
        missA = sum(1 for i in ft if J[i["id"]][0] == "pass" and i["truth"] == "fail")
        out["B_by_family"][fam] = {"n": len(ft), "missed_A": stats.rate(missA, nf), "missed_B": stats.rate(miss, nf), "queue_B": stats.rate(q, len(ft))}
    # unsure as a signal: error rate of sure vs unsure judgments
    sure_wrong = [J[i["id"]][0] != i["truth"] for i in test if confidence(st, i["id"], a, 1) == "sure"]
    unsure_wrong = [J[i["id"]][0] != i["truth"] for i in test if confidence(st, i["id"], a, 1) == "unsure"]
    out["error_rate_sure"] = stats.rate(sum(sure_wrong), len(sure_wrong))
    out["error_rate_unsure"] = stats.rate(sum(unsure_wrong), len(unsure_wrong))
    return out


# ------------------------------------------------------------------------------------------- 7.7 perturbations
def perturbations(items, st_main, a, J):
    pert = store("perturb")
    by_id = {i["id"]: i for i in items}
    ids = sorted({k.split("|")[1] for k in pert})
    out = {}
    noise = [J[i][0] != J[i][1] for i in ids if i in J]
    out["noise_floor"] = stats.rate(sum(noise), len(noise))
    for cond in ("r1", "r2", "swap", "verbose", "assertive", "low"):
        rows = []
        for iid in ids:
            r = pert.get(f"pert|{iid}|{cond}")
            if r is None or iid not in J or r.get("output") is None:
                continue
            it = by_id[iid]
            rows.append((it, J[iid][0], prompts.verdict_of(it, a, r["output"]), r))
        flips = sum(1 for _, base, v, _ in rows if base != v)
        right_base = [base == it["truth"] for it, base, _, _ in rows]
        right_new = [v == it["truth"] for it, _, v, _ in rows]
        b = sum(1 for x, y in zip(right_base, right_new) if x and not y)
        c = sum(1 for x, y in zip(right_base, right_new) if y and not x)
        wrong_c = [(base, v) for it, base, v, _ in rows if it["truth"] == "fail"]
        right_c = [(base, v) for it, base, v, _ in rows if it["truth"] == "pass"]
        out[cond] = {"n": len(rows), "flip": stats.rate(flips, len(rows)),
                     "accuracy_base": stats.rate(sum(right_base), len(rows)), "accuracy_new": stats.rate(sum(right_new), len(rows)),
                     "mcnemar_p": stats.mcnemar_exact(b, c),
                     "wrong_pass_base": stats.rate(sum(1 for x, _ in wrong_c if x == "pass"), len(wrong_c)),
                     "wrong_pass_new": stats.rate(sum(1 for _, y in wrong_c if y == "pass"), len(wrong_c)),
                     "right_pass_base": stats.rate(sum(1 for x, _ in right_c if x == "pass"), len(right_c)),
                     "right_pass_new": stats.rate(sum(1 for _, y in right_c if y == "pass"), len(right_c)),
                     "cost_per_call": mean_cost([r for *_, r in rows])}
        out[cond]["by_family"] = {}
        for fam in prompts.BINARY:
            fr = [(it, base, v) for it, base, v, _ in rows if it["family"] == fam]
            out[cond]["by_family"][fam] = {"n": len(fr), "flip": stats.rate(sum(1 for _, x, y in fr if x != y), len(fr))}
    base_cost = mean_cost([st_main[f"main|{i}|{a}|r1"] for i in ids if f"main|{i}|{a}|r1" in st_main])
    out["base_cost_per_call"] = base_cost
    return out


# ------------------------------------------------------------------------------------------- 7.8 pairs and lists
def pairs_lists(items, a, J):
    import run as R

    st = store("pair")
    pr = R.pairs(items)
    rows = []
    for pid, right, wrong in pr:
        ab, ba = st.get(f"pair|{pid}|AB"), st.get(f"pair|{pid}|BA")
        if not ab or not ba or ab.get("output") is None or ba.get("output") is None:
            continue
        ok_ab = ab["output"]["right"] == "A"   # right shown first
        ok_ba = ba["output"]["right"] == "B"   # right shown second
        rows.append({"pid": pid, "family": right["family"], "first": ok_ab, "second": ok_ba,
                     "consistent": ok_ab == ok_ba, "picked_A_both": ab["output"]["right"] == "A" and ba["output"]["right"] == "A",
                     "picked_B_both": ab["output"]["right"] == "B" and ba["output"]["right"] == "B",
                     "single_right": J.get(right["id"], [None])[0] == "pass" and J.get(wrong["id"], [None])[0] == "fail"})
    n = len(rows)
    out = {"pairs": {"n": n, "right_first": stats.rate(sum(r["first"] for r in rows), n), "right_second": stats.rate(sum(r["second"] for r in rows), n),
                     "consistent": stats.rate(sum(r["consistent"] for r in rows), n),
                     "inconsistent_picks_A": sum(r["picked_A_both"] for r in rows), "inconsistent_picks_B": sum(r["picked_B_both"] for r in rows),
                     "single_item_both_right": stats.rate(sum(r["single_right"] for r in rows), n),
                     "mcnemar_first_vs_second": stats.mcnemar_exact(sum(1 for r in rows if r["first"] and not r["second"]), sum(1 for r in rows if r["second"] and not r["first"])),
                     "by_family": {}}}
    for fam in ("review", "suggest"):
        fr = [r for r in rows if r["family"] == fam]
        out["pairs"]["by_family"][fam] = {"n": len(fr), "right_first": stats.rate(sum(r["first"] for r in fr), len(fr)),
                                          "right_second": stats.rate(sum(r["second"] for r in fr), len(fr)),
                                          "consistent": stats.rate(sum(r["consistent"] for r in fr), len(fr))}
    st = store("list")
    groups = R.lists(items)
    agree = right_list = right_single = n = 0
    for c, group in groups.items():
        fwd, rev = st.get(f"list|{c}|fwd"), st.get(f"list|{c}|rev")
        if not fwd or not rev or fwd.get("output") is None or rev.get("output") is None:
            continue
        def verdicts(res, order):
            got = {}
            for x in res["output"]["results"]:
                k = x["n"] - 1
                if 0 <= k < len(order):
                    got[order[k]["id"]] = prompts.verdict_of(order[k], a, x)
            return got
        vf, vr = verdicts(fwd, group), verdicts(rev, list(reversed(group)))
        for it in group:
            if it["id"] in vf and it["id"] in vr:
                n += 1
                agree += vf[it["id"]] == vr[it["id"]]
                right_list += vf[it["id"]] == it["truth"]
                right_single += J.get(it["id"], [None])[0] == it["truth"]
    out["lists"] = {"verdicts": n, "same_in_both_orders": stats.rate(agree, n), "accuracy_in_list": stats.rate(right_list, n),
                    "accuracy_single": stats.rate(right_single, n), "lists": len(groups)}
    return out


# ------------------------------------------------------------------------------------------- 7.9 QC agent
def qc_section(items):
    path = OUT / "qc-agent.jsonl"
    if not path.exists():
        return None
    res = {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}
    recs = [json.loads(l) for l in (ROOT / "data" / "items" / "qc.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if r["split"] == "test"]
    import qc as Q

    rows = []
    for r in recs:
        script = bool(rules.review_problems(r["material"], Q.as_review(r["candidate"])))
        o = res.get(r["id"], {})
        agent = (o.get("output") or {}).get("verdict") == "wrong"
        rows.append({"r": r, "script": script, "agent": agent, "answered": o.get("output") is not None,
                     "pipeline": script or agent, "cost": o.get("usage", {}).get("cost_usd", 0.0),
                     "unsure": (o.get("output") or {}).get("confidence") == "unsure", "tools": o.get("tool_calls", []),
                     "problem": (o.get("output") or {}).get("problem")})
    wrong = [x for x in rows if x["r"]["truth"] == "fail"]
    right = [x for x in rows if x["r"]["truth"] == "pass"]
    out = {"records": len(rows), "answered": sum(x["answered"] for x in rows), "wrong": len(wrong), "correct": len(right)}
    for arm in ("script", "agent", "pipeline"):
        out[arm] = {"caught": stats.rate(sum(x[arm] for x in wrong), len(wrong)),
                    "false_flags": stats.rate(sum(x[arm] for x in right), len(right)), "by_type": {}}
        for t in Q.ERROR_TYPES:
            tw = [x for x in wrong if x["r"]["dimension"] == t]
            out[arm]["by_type"][t] = stats.rate(sum(x[arm] for x in tw), len(tw))
    out["agent_cost_per_record"] = statistics.mean(x["cost"] for x in rows)
    out["pipeline_cost_per_record"] = statistics.mean(x["cost"] if not x["script"] else 0.0 for x in rows)
    out["tool_calls_per_record"] = statistics.mean(len(x["tools"]) for x in rows)
    out["records_without_tool_call"] = sum(1 for x in rows if not x["tools"])
    tp = [x for x in wrong if x["agent"]]
    out["problem_named_right"] = stats.rate(sum(1 for x in tp if x["problem"] == {"decision": "decision", "category": "category_or_clause",
                                                                                     "span_semantic": "span", "span_altered": "span", "unknown_clause": "format"}[x["r"]["dimension"]]
                                                 or (x["r"]["dimension"] == "unknown_clause" and x["problem"] == "category_or_clause")), len(tp))
    # acceptance standard, operating characteristic
    rng = np.random.default_rng(stats.SEED)
    N, SPOT = 100, 20
    oc = {}
    for p in (0.0, 0.01, 0.02, 0.05, 0.10, 0.20):
        acc, s_fail = 0, Counter()
        for _ in range(2000):
            n_err = rng.binomial(N, p)
            batch = [wrong[k] for k in rng.integers(0, len(wrong), n_err)] + [right[k] for k in rng.integers(0, len(right), N - n_err)]
            script_bad = sum(x["script"] for x in batch)
            rest = [x for x in batch if not x["script"]]
            flagged = sum(x["agent"] for x in rest)
            unflagged = [x for x in rest if not x["agent"]]
            spot = [unflagged[k] for k in rng.choice(len(unflagged), min(SPOT, len(unflagged)), replace=False)] if unflagged else []
            s1 = script_bad <= 0.02 * N
            s2 = flagged <= 0.10 * len(rest) if rest else True
            s3 = sum(x["r"]["truth"] == "fail" for x in spot) <= 1
            acc += s1 and s2 and s3
            s_fail.update([k for k, ok in (("S1", s1), ("S2", s2), ("S3", s3)) if not ok])
        oc[f"{p:.2f}"] = {"accepted": acc / 2000, "failed_S1": s_fail["S1"] / 2000, "failed_S2": s_fail["S2"] / 2000, "failed_S3": s_fail["S3"] / 2000}
    out["acceptance"] = oc
    out["targets_met"] = {"accept_at_<=2%": all(oc[k]["accepted"] >= 0.9 for k in ("0.00", "0.01", "0.02")),
                          "reject_at_>=10%": all(oc[k]["accepted"] <= 0.1 for k in ("0.10", "0.20"))}
    return out


# ------------------------------------------------------------------------------------------- cost
def costs():
    out = {}
    for p in sorted(RAW.glob("*.jsonl")):
        if p.name.endswith(".journal.jsonl"):
            continue
        out[p.stem] = llm.total_cost(p)
    out["total_usd"] = round(sum(v["cost_usd"] for v in out.values()), 4)
    return out


def main() -> int:
    items = load_all()
    if len(sys.argv) > 1 and sys.argv[1] == "adopt":
        res = adopt(items)
        if not REGISTERED:   # the adopted version is the registered one (v2); the corrected dev run is reported, not used
            raise SystemExit("adopt reads the registered dev answers only: run with --as-registered")
        ADOPTED.write_text(json.dumps(clean(res), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        for v, t in res["table"].items():
            print(v, "score", round(t["score"], 4), "cost/call", round(t["cost_per_call"], 6), "answered", t["answered"], "/", t["expected"],
                  {f: (round(x["pass_recall"]["rate"], 3), round(x["fail_recall"]["rate"], 3)) for f, x in t["families"].items()})
        for s in res["steps"]:
            print(s)
        print("adopted:", res["version"])
        return 0
    a = json.loads(ADOPTED.read_text(encoding="utf-8"))["version"]
    st = store("main")
    summary = {"adopted": a, "dev": json.loads(ADOPTED.read_text(encoding="utf-8")), "registered": REGISTERED}
    if not REGISTERED:
        summary["dev_c1"] = clean(adopt(items))   # the adoption rule on the corrected dev answers (reported only)
    binr, J = binary_section(items, st, a)
    reg, JR = regulator_section(items, st)
    jv, _ = jv_section(items, st)
    se, _ = summeval_section(items, st)
    mq, _ = mqm_section(items, st)
    summary.update(binary=binr, regulator=reg, jv=jv, summeval=se, mqm=mq)
    summary["grouping"] = grouping(binr, reg, jv, se, mq)
    summary["combination"] = combination(items, st, a, J)
    if (RAW / "perturb.jsonl").exists():
        summary["perturb"] = perturbations(items, st, a, J)
    if (RAW / "pair.jsonl").exists():
        summary["pairs_lists"] = pairs_lists(items, a, J)
    summary["qc"] = qc_section(items)
    summary["second_judge"] = second_judge(items)
    summary["cost"] = costs()
    summary["predictions"] = predictions(summary)
    summary["details"] = details(items, st, a, J, JR, summary)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / ("summary.registered.json" if REGISTERED else "summary.json")).write_text(json.dumps(clean(summary), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("wrote", OUT / ("summary.registered.json" if REGISTERED else "summary.json"), "| total cost", summary["cost"]["total_usd"])
    return 0


def details(items, st, a, J, JR, s):
    """Counts the report text uses that are not in a table: what the misses were, and derived totals."""
    by_id = {i["id"]: i for i in items}
    d = {}
    test = [i for i in items if i["split"] == "test" and i["family"] in prompts.BINARY and i["id"] in J]
    miss = [i for i in test if majority(J[i["id"]]) != i["truth"]]
    d["constructed_disagreements"] = len(miss)
    flips_passed = [i for i in miss if i["dimension"] == "decision"]
    d["argued_wrong_decision_passed"] = len(flips_passed)
    d["argued_wrong_decision_passed_first_unsure"] = sum(1 for i in flips_passed if confidence(st, i["id"], a, 1) == "unsure")
    d["swapped_clause_passed"] = sum(1 for i in miss if i["dimension"] == "clause")
    d["right_review_of_trap_ad_failed"] = sum(1 for i in miss if i["family"] == "review" and i["truth"] == "pass" and i["meta"].get("trap"))
    ki = json.loads((OUT / "key_issues.json").read_text(encoding="utf-8")) if (OUT / "key_issues.json").exists() else {}
    miss_ids = {i["id"] for i in miss}
    d["disagreements_material_gap"] = sum(1 for x in ki.get("material_gap", []) if x["holds"] and x["item"] in miss_ids)
    d["disagreements_answer_key"] = sum(1 for x in ki.get("extra_violation", []) if x["holds"] and x["item"] in miss_ids)
    d["disagreements_left_to_judge"] = d["constructed_disagreements"] - d["disagreements_material_gap"] - d["disagreements_answer_key"]
    reg = [i for i in items if i["family"] == "regulator" and i["id"] in JR]
    rmiss = [i for i in reg if majority(JR[i["id"]]) != i["truth"]]
    d["regulator_misses"] = len(rmiss)
    d["regulator_misses_evidence_dependent"] = sum(1 for i in rmiss if i["dimension"] == "evidence_dependent")
    jvc = s["jv"]["confusion"]
    d["jv_median_half_items"] = sum(v for k, v in jvc.items() if k.startswith("truth 1 "))
    d["jv_median_half_judge_half"] = jvc.get("truth 1 judge 1", 0)
    pert = store("perturb")
    r2 = []
    for k, r in pert.items():
        _, iid, cond = k.split("|")
        if cond == "r2" and iid in J and r.get("output"):
            it = by_id[iid]
            if prompts.verdict_of(it, a, r["output"]) != J[iid][0]:
                r2.append(it)
    good_failed = [i for i in r2 if i["truth"] == "pass"]
    d["terse_rubric_good_suggestions_failed"] = len(good_failed)
    d["terse_rubric_good_failed_empty_rewrite"] = sum(1 for i in good_failed if not i["candidate"].get("rewrite", "").strip())
    d["terse_rubric_bad_suggestions_passed"] = sum(1 for i in r2 if i["truth"] == "fail")
    if s.get("qc"):
        res = {json.loads(l)["id"]: json.loads(l) for l in (OUT / "qc-agent.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
        recs = [json.loads(l) for l in (ROOT / "data" / "items" / "qc.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        ff = [res[r["id"]]["output"]["problem"] for r in recs if r["split"] == "test" and r["truth"] == "pass" and (res[r["id"]].get("output") or {}).get("verdict") == "wrong"]
        d["qc_false_flags_by_problem"] = dict(Counter(ff))
        d["qc_records_settled_by_script"] = sum(1 for r in recs if r["split"] == "test" and rules.review_problems(r["material"], __import__("qc").as_review(r["candidate"])))
    sec = store("second")
    if sec:
        main = st
        hk = [main[f"main|{k.split('|')[1]}|{k.split('|')[2]}|r1"]["cost_usd"] for k in sec]
        sn = [r["cost_usd"] for r in sec.values()]
        d["second_judge_items_haiku_usd_per_1000"] = sum(hk) / len(hk) * 1000
        d["second_judge_usd_per_1000"] = sum(sn) / len(sn) * 1000
        d["second_judge_price_ratio"] = sum(sn) / sum(hk)
        none_items = [k for k in sec if by_id[k.split("|")[1]]["family"] == "mqm" and by_id[k.split("|")[1]]["truth"] == "none"]
        d["second_judge_mqm_clean_items"] = len(none_items)
        d["second_judge_mqm_clean_called_flawed"] = sum(1 for k in none_items if sec[k]["output"]["verdict"] != "none")
    c = s["cost"]
    d["spend_before_second_judge_usd"] = sum(v["cost_usd"] for k, v in c.items() if isinstance(v, dict) and not k.startswith("second") and not k.endswith("-c1"))
    d["correction_c1_calls"] = sum(v["calls"] for k, v in c.items() if isinstance(v, dict) and k.endswith("-c1"))
    d["correction_c1_usd"] = sum(v["cost_usd"] for k, v in c.items() if isinstance(v, dict) and k.endswith("-c1"))
    # the perturbation flips of the corrected suggest items, by item, to show which items flip under which change
    flips = {}
    for k, r in pert.items():
        _, iid, cond = k.split("|")
        if iid in J and r.get("output") and by_id[iid]["family"] == "suggest":
            if prompts.verdict_of(by_id[iid], a, r["output"]) != J[iid][0]:
                flips.setdefault(iid, []).append(cond)
    d["suggest_perturb_flips_by_item"] = flips
    d["total_calls"] = sum(v["calls"] for v in c.values() if isinstance(v, dict))
    d["second_judge_calls_with_estimate"] = sum(v["calls"] for k, v in c.items() if isinstance(v, dict) and k in ("second", "second-estimate"))
    d["second_judge_usd_with_estimate"] = sum(v["cost_usd"] for k, v in c.items() if isinstance(v, dict) and k in ("second", "second-estimate"))
    d["judge_usd_per_1000"] = {f: v * 1000 for f, v in s["binary"]["cost_per_call"].items()}
    d["combination_extra_queue_C_over_B"] = s["combination"]["C"]["queue"]["k"] - s["combination"]["B"]["queue"]["k"]
    d["combination_queue_B_review"] = s["combination"]["B_by_family"]["review"]["queue_B"]["k"]
    src = OUT / "source_stats.json"
    if src.exists():
        d["source_stats"] = json.loads(src.read_text(encoding="utf-8"))
    return d


def second_judge(items):
    st = store("second")
    if not st:
        return None
    by_id = {i["id"]: i for i in items}
    main = store("main")
    rows = []
    for k, r in st.items():
        iid = k.split("|")[1]
        it = by_id[iid]
        ver = "fixed" if it["family"] == "mqm" else json.loads(ADOPTED.read_text(encoding="utf-8"))["version"]
        base = main.get(f"main|{iid}|{ver}|r1")
        if r.get("output") is None or base is None or base.get("output") is None:
            continue
        rows.append((it, prompts.verdict_of(it, ver, r["output"]), prompts.verdict_of(it, ver, base["output"]), r))
    out = {"n": len(rows), "by_family": {}}
    for fam in sorted({it["family"] for it, *_ in rows}):
        fr = [x for x in rows if x[0]["family"] == fam]
        out["by_family"][fam] = {"n": len(fr), "sonnet_right": stats.rate(sum(1 for it, s, _, _ in fr if s == it["truth"]), len(fr)),
                                 "haiku_right": stats.rate(sum(1 for it, _, hk, _ in fr if hk == it["truth"]), len(fr)),
                                 "same_verdict": stats.rate(sum(1 for _, s, hk, _ in fr if s == hk), len(fr)),
                                 "mcnemar_p": stats.mcnemar_exact(sum(1 for it, s, hk, _ in fr if hk == it["truth"] and s != it["truth"]),
                                                                  sum(1 for it, s, hk, _ in fr if s == it["truth"] and hk != it["truth"]))}
    out["sonnet_cost_per_call"] = mean_cost([r for *_, r in rows])
    return out


def predictions(s):
    P = {}
    b = s["binary"]
    P[1] = ("judge alone catches < 95% of rule-checkable errors", b["judge_on_rule_checkable"]["rate"] < 0.95)
    P[2] = ("regulator agreement lower than constructed agreement", s["regulator"]["overall"]["agreement"]["rate"] < b["pooled"]["agreement"]["rate"])
    r = s["regulator"]["by_dimension"]
    P[3] = ("lower on evidence-dependent decisions", r.get("evidence_dependent", {}).get("agreement", {}).get("rate", 1) < r.get("on_the_face", {}).get("agreement", {}).get("rate", 0))
    jv = s["jv"]
    P[4] = ("jv: judge mean pairwise exact agreement within the human range", jv["human_range_exact"][0] <= jv["judge_mean_exact"] <= jv["human_range_exact"][1])
    P[5] = ("summeval: judge below the expert ceiling on all four dimensions", all(x["spearman"] < x["expert_ceiling_spearman"] for x in s["summeval"].values()))
    human_stab = statistics.mean([jv["stability"]["rate"], s["mqm"]["stability"]["rate"]] + [x["all_three_same"]["rate"] for x in s["summeval"].values()])
    P[6] = ("three judgments identical less often on human-rated families", human_stab < b["stability_all_three_same"]["rate"])
    if "perturb" in s:
        pa = s["perturb"]["assertive"]
        P[7] = ("assurance raises the pass rate of wrong candidates by >= 2 points", pa["wrong_pass_new"]["rate"] - pa["wrong_pass_base"]["rate"] >= 0.02)
        P[8] = ("rewording flips more verdicts than repeating", min(s["perturb"]["r1"]["flip"]["rate"], s["perturb"]["r2"]["flip"]["rate"]) > s["perturb"]["noise_floor"]["rate"])
    if "pairs_lists" in s:
        P[9] = ("pairs: same pick in both orders >= 90%", s["pairs_lists"]["pairs"]["consistent"]["rate"] >= 0.9)
    c = s["combination"]
    P[10] = ("B misses fewer errors than A with a queue <= 20%", c["B"]["missed"]["k"] < c["A"]["missed"]["k"] and c["B"]["queue"]["rate"] <= 0.2)
    if s.get("qc"):
        q = s["qc"]["pipeline"]
        P[11] = ("script then agent catches >= 90% and flags <= 10% of correct records", q["caught"]["rate"] >= 0.9 and q["false_flags"]["rate"] <= 0.1)
        P[12] = ("acceptance standard meets both targets", all(s["qc"]["targets_met"].values()))
    return {k: {"prediction": v[0], "held": bool(v[1])} for k, v in P.items()}


if __name__ == "__main__":
    sys.exit(main())
