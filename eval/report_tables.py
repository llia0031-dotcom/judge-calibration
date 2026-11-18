"""Writes eval/results/RESULTS.md: every table of the report, generated from summary.json (no model calls)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT / "eval" / "results" / "summary.json").read_text(encoding="utf-8"))


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


def rate(r, d=1):
    if not r or r.get("n", 0) == 0:
        return "–"
    return f"{r['k']}/{r['n']} ({pct(r['rate'], d)}; {pct(r['lo'], d)}–{pct(r['hi'], d)})"


def num(x, d=3):
    return "–" if x is None else f"{x:.{d}f}"


def kap(k):
    return f"{num(k['kappa'])} ({num(k['lo'])}–{num(k['hi'])})"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> int:
    L = [f"# Results (generated from summary.json)\n\nAdopted judge prompt: {S['adopted']}. Intervals are 95% (Wilson for proportions, cluster bootstrap for kappas).\n"]
    # dev
    rows = []
    for v, t in S["dev"]["table"].items():
        f = t["families"]
        rows.append([v, num(t["score"]), *[f"{pct(f[x]['pass_recall']['rate'])} / {pct(f[x]['fail_recall']['rate'])}" for x in ("review", "claim", "suggest")],
                     f"{t['cost_per_call'] * 1000:.3f}"])
    L += ["## 1. Prompt versions on the development split\n", table(["Version", "Score (mean BA)", "review pass / fail recall", "claim", "suggest", "USD per 1,000 calls"], rows), ""]
    L.append("Adoption steps: " + "; ".join(f"{s['candidate']} vs {s['against']}: {'adopted' if s['adopted'] else 'not adopted (' + ', '.join(k for k, v in s['checks'].items() if not v) + ')'}" for s in S["dev"]["steps"]) + "\n")
    # constructed
    b = S["binary"]
    rows = []
    for fam, f in b["families"].items():
        o = f["overall"]
        rows.append([fam, o["n"], rate(o["agreement"]), kap(o["kappa"]), num(o["ac1"]), rate(o["fail_recall"]), rate(o["pass_recall"]),
                     rate(f["stability"]["all_three_same"]), num(f["stability"]["fleiss"])])
    o = b["pooled"]
    rows.append(["all", o["n"], rate(o["agreement"]), kap(o["kappa"]), num(o["ac1"]), rate(o["fail_recall"]), rate(o["pass_recall"]), rate(b["stability_all_three_same"]), ""])
    L += ["## 2. Constructed answers (test split, majority of three judgments)\n",
          table(["Family", "Items", "Agreement", "Cohen's kappa", "AC1", "Errors caught", "Right ones passed", "Three judgments identical", "Fleiss' kappa"], rows), ""]
    rows = []
    for fam, f in b["families"].items():
        for d, x in f["by_dimension"].items():
            rows.append([fam, d, x["n"], rate(x["right"]), rate(f["stability_by_dimension"][d])])
    L += ["### By error type\n\n`correct` rows are right candidates (share passed); the others are planted errors (share caught).\n",
          table(["Family", "Type", "Items", "Judged right", "Identical ×3"], rows), ""]
    rows = []
    for fam, f in b["families"].items():
        for key in ("by_lang", "by_modality"):
            for g, x in f[key].items():
                rows.append([fam, g, x["n"], rate(x["right"]), pct(x["pass_recall"]["rate"]), pct(x["fail_recall"]["rate"])])
    L += ["### By language and modality\n", table(["Family", "Group", "Items", "Judged right", "Pass recall", "Fail recall"], rows), ""]
    rows = [[fam, f["v1_single"]["n"], pct(f["v1_single"]["pass_recall"]["rate"]), pct(f["v1_single"]["fail_recall"]["rate"]),
             pct(f["adopted_single"]["pass_recall"]["rate"]), pct(f["adopted_single"]["fail_recall"]["rate"])] for fam, f in b["families"].items()]
    L += [f"### v1 against {S['adopted']} on the test split (one judgment each)\n", table(["Family", "Items", "v1 pass recall", "v1 fail recall", f"{S['adopted']} pass recall", f"{S['adopted']} fail recall"], rows), ""]
    L.append(f"Judge alone on rule-checkable errors: {rate(b['judge_on_rule_checkable'])} caught ("
             + ", ".join(f"{fam} {rate(f['judge_on_rule_checkable'])}" for fam, f in b["families"].items() if "judge_on_rule_checkable" in f) + ").\n")
    # regulator
    r = S["regulator"]
    rows = [["all", r["overall"]["n"], rate(r["overall"]["agreement"]), kap(r["overall"]["kappa"]), rate(r["overall"]["fail_recall"]), rate(r["overall"]["pass_recall"])]]
    for key in ("by_lang", "by_dimension"):
        for g, x in r[key].items():
            rows.append([g, x["n"], rate(x["agreement"]), "", rate(x["fail_recall"]), rate(x["pass_recall"])])
    L += ["## 3. Regulator and court decisions\n", table(["Group", "Ads", "Agreement", "Kappa", "Breaches found", "Cleared ads cleared"], rows), "",
          f"AC1: {num(r['overall']['ac1'])}. Three judgments identical: {rate(r['stability'])}. First judgment marked unsure: {rate(r['unsure_share'])}.\n"]
    # human
    jv = S["jv"]
    L += ["## 4. Human ratings that ship with public datasets\n", "### Judge's Verdict (0 / 0.5 / 1, three annotators)\n",
          table(["Measure", "Value"], [["Judge vs annotators' median, exact", rate(jv["exact"])], ["Judge vs median, weighted kappa", kap(jv["weighted_kappa"])],
                                       ["Annotator pairs, exact agreement (min–max)", f"{pct(jv['human_range_exact'][0])}–{pct(jv['human_range_exact'][1])} (mean {pct(jv['human_mean_exact'])})"],
                                       ["Judge vs each annotator, exact (mean)", pct(jv["judge_mean_exact"])],
                                       ["Annotator pairs, weighted kappa (min–max)", f"{num(jv['human_range_wkappa'][0])}–{num(jv['human_range_wkappa'][1])} (mean {num(jv['human_mean_wkappa'])})"],
                                       ["Judge vs each annotator, weighted kappa (mean)", num(jv["judge_mean_wkappa"])],
                                       ["Three judgments identical", rate(jv["stability"])]]), ""]
    rows = [[d, x["n"], rate(x["exact"]), num(x["weighted_kappa"])] for d, x in jv["by_dimension"].items()]
    L += [table(["Annotators", "Items", "Exact", "Weighted kappa"], rows), ""]
    rows = [[d, x["n"], f"{num(x['spearman'])} ({num(x['spearman_lo'])}–{num(x['spearman_hi'])})", num(x["kendall"]), num(x["expert_ceiling_spearman"]),
             num(x["crowd_vs_expert_spearman"]), f"{x['judge_mean']:.2f} / {x['expert_mean']:.2f}", rate(x["stable_within_1"])] for d, x in S["summeval"].items()]
    L += ["### SummEval (1–5, three experts)\n", table(["Dimension", "Items", "Spearman (judge vs experts)", "Kendall", "Expert ceiling", "Crowd vs experts", "Mean score judge / experts", "Three judgments within 1"], rows), ""]
    m = S["mqm"]
    rows = [["Exact (3 classes)", rate(m["exact"])], ["Weighted kappa", kap(m["weighted_kappa"])],
            *[[f"Recall: {c}", rate(x)] for c, x in m["recall"].items()], ["Any error found (minor or major)", rate(m["any_error_recall"])],
            ["Three judgments identical", rate(m["stability"])]]
    L += ["### WMT MQM, Chinese to English\n", table(["Measure", "Value"], rows), ""]
    rows = [[d, x["n"], rate(x["exact"]), num(x["weighted_kappa"])] for d, x in m["by_domain"].items()]
    L += [table(["Domain", "Items", "Exact", "Weighted kappa"], rows), "", "Confusion (truth, judge; 0 none, 1 minor, 2 major): " + ", ".join(f"{k}: {v}" for k, v in m["confusion"].items()) + "\n"]
    # grouping
    rows = [[g["family"], g["dimension"], g["metric"], num(g["value"]), pct(g["stable"]), g["group"]] for g in S["grouping"]]
    L += ["## 5. Objective errors, subjective ratings: what can be left to whom\n", table(["Family", "Dimension", "Measure", "Value", "Stable", "Group"], rows), ""]
    # combination
    c = S["combination"]
    rows = [[arm, rate(c[arm]["coverage"]), rate(c[arm]["missed"]), rate(c[arm]["false_alarms"]), rate(c[arm]["queue"]), c[arm]["judge_calls"],
             f"{c[arm]['cost_per_1000_items']:.3f}"] for arm in ("A", "B", "C")]
    L += ["## 6. Rules, judge and a review queue\n", "A judge only; B rules then one judgment, unsure to the queue; C rules then two judgments, unsure or split to the queue.\n",
          table(["Arm", "Decided automatically", "Errors missed", "False alarms", "Queue", "Judge calls", "USD per 1,000 items"], rows), ""]
    rows = [[fam, rate(x["missed_A"]), rate(x["missed_B"]), rate(x["queue_B"])] for fam, x in c["B_by_family"].items()]
    L += [table(["Family", "Missed, A", "Missed, B", "Queue, B"], rows), "", f"Error rate of first judgments marked sure: {rate(c['error_rate_sure'])}; marked unsure: {rate(c['error_rate_unsure'])}.\n"]
    # perturbations
    if "perturb" in S:
        p = S["perturb"]
        rows = [["repeat (noise floor)", p["noise_floor"]["n"], rate(p["noise_floor"]), "", "", "", ""]]
        for cond in ("r1", "r2", "swap", "verbose", "assertive", "low"):
            x = p[cond]
            rows.append([cond, x["n"], rate(x["flip"]), f"{pct(x['accuracy_base']['rate'])} → {pct(x['accuracy_new']['rate'])}", num(x["mcnemar_p"]),
                         f"{pct(x['wrong_pass_base']['rate'])} → {pct(x['wrong_pass_new']['rate'])}", f"{x['cost_per_call'] * 1000:.3f}"])
        L += ["## 7. Sensitivity\n", "r1 reworded rubric in another order; r2 terse rubric; swap answer options in the other order; verbose a long content-free passage added to the candidate; assertive one sentence of assurance added; low effort low.\n",
              table(["Change", "Items", "Verdicts changed", "Accuracy before → after", "McNemar p", "Wrong ones passed before → after", "USD per 1,000 calls"], rows), "",
              f"Base cost per call on this subsample: {p['base_cost_per_call'] * 1000:.3f} USD per 1,000 calls.\n"]
        rows = [[cond, *[rate(p[cond]["by_family"][f]["flip"]) for f in ("review", "claim", "suggest")]] for cond in ("r1", "r2", "swap", "verbose", "assertive", "low")]
        L += [table(["Change", "review", "claim", "suggest"], rows), ""]
    if "pairs_lists" in S:
        pp, ll = S["pairs_lists"]["pairs"], S["pairs_lists"]["lists"]
        rows = [["all", pp["n"], rate(pp["right_first"]), rate(pp["right_second"]), rate(pp["consistent"])]]
        rows += [[f, x["n"], rate(x["right_first"]), rate(x["right_second"]), rate(x["consistent"])] for f, x in pp["by_family"].items()]
        L += ["## 8. Position and order\n", table(["Pairs", "Pairs", "Right when shown first", "Right when shown second", "Same pick both orders"], rows), "",
              f"Inconsistent pairs: picked A both times {pp['inconsistent_picks_A']}, picked B both times {pp['inconsistent_picks_B']}. McNemar (first vs second) p = {num(pp['mcnemar_first_vs_second'])}. "
              f"Both items judged right one at a time: {rate(pp['single_item_both_right'])}.\n",
              f"Lists ({ll['lists']} resumes, {ll['verdicts']} verdicts): same verdict in both orders {rate(ll['same_in_both_orders'])}; accuracy in lists {rate(ll['accuracy_in_list'])} against one at a time {rate(ll['accuracy_single'])}.\n"]
    q = S.get("qc")
    if q:
        rows = [[arm, rate(q[arm]["caught"]), rate(q[arm]["false_flags"]), *[rate(q[arm]["by_type"][t]) for t in ("decision", "category", "span_semantic", "span_altered", "unknown_clause")]]
                for arm in ("script", "agent", "pipeline")]
        L += ["## 9. Quality-check agent\n", f"{q['records']} test records ({q['wrong']} with one planted error, {q['correct']} correct).\n",
              table(["Check", "Wrong records caught", "Correct records flagged", "decision", "category", "span_semantic", "span_altered", "unknown_clause"], rows), "",
              f"Agent: {q['tool_calls_per_record']:.2f} tool calls per record ({q['records_without_tool_call']} records with none); problem named right on {rate(q['problem_named_right'])} of the wrong records it caught; "
              f"{q['agent_cost_per_record'] * 1000:.3f} USD per 1,000 records alone, {q['pipeline_cost_per_record'] * 1000:.3f} after the script.\n"]
        rows = [[f"{float(k):.0%}", pct(v["accepted"]), pct(v["failed_S1"]), pct(v["failed_S2"]), pct(v["failed_S3"])] for k, v in q["acceptance"].items()]
        L += ["### Acceptance standard, simulated batches of 100 records\n", table(["True error rate", "Accepted", "Failed S1", "Failed S2", "Failed S3"], rows), "",
              "Targets: " + ", ".join(f"{k}: {'met' if v else 'not met'}" for k, v in q["targets_met"].items()) + "\n"]
    sj = S.get("second_judge")
    if sj:
        rows = [[f, x["n"], rate(x["haiku_right"]), rate(x["sonnet_right"]), rate(x["same_verdict"]), num(x["mcnemar_p"])] for f, x in sj["by_family"].items()]
        L += ["## 10. A second judge (claude-sonnet-5-5, one judgment)\n", table(["Family", "Items", "claude-haiku-5-5 right", "claude-sonnet-5-5 right", "Same verdict", "McNemar p"], rows), "",
              f"claude-sonnet-5-5 cost {sj['sonnet_cost_per_call'] * 1000:.3f} USD per 1,000 calls (batch price).\n"]
    RP = ROOT / "eval" / "results" / "summary.registered.json"
    if RP.exists() and not S.get("registered"):
        R = json.loads(RP.read_text(encoding="utf-8"))
        bs, br = S["binary"], R["binary"]
        fs, fr = bs["families"]["suggest"], br["families"]["suggest"]

        def pair_row(name, get):
            try:
                return [name, get(R), get(S)]
            except (KeyError, TypeError):
                return [name, "–", "–"]
        rows = [
            pair_row("suggest: agreement", lambda X: rate(X["binary"]["families"]["suggest"]["overall"]["agreement"])),
            pair_row("suggest: right ones passed", lambda X: rate(X["binary"]["families"]["suggest"]["overall"]["pass_recall"])),
            pair_row("suggest: errors caught", lambda X: rate(X["binary"]["families"]["suggest"]["overall"]["fail_recall"])),
            pair_row("suggest: Cohen's kappa", lambda X: kap(X["binary"]["families"]["suggest"]["overall"]["kappa"])),
            pair_row("suggest: three judgments identical", lambda X: rate(X["binary"]["families"]["suggest"]["stability"]["all_three_same"])),
            pair_row("suggest: v1 pass / fail recall (one judgment)", lambda X: f"{pct(X['binary']['families']['suggest']['v1_single']['pass_recall']['rate'])} / {pct(X['binary']['families']['suggest']['v1_single']['fail_recall']['rate'])}"),
            pair_row("all constructed: agreement", lambda X: rate(X["binary"]["pooled"]["agreement"])),
            pair_row("all constructed: Cohen's kappa", lambda X: kap(X["binary"]["pooled"]["kappa"])),
            pair_row("all constructed: errors caught", lambda X: rate(X["binary"]["pooled"]["fail_recall"])),
            pair_row("all constructed: right ones passed", lambda X: rate(X["binary"]["pooled"]["pass_recall"])),
            pair_row("all constructed: three judgments identical", lambda X: rate(X["binary"]["stability_all_three_same"])),
            pair_row("disagreements (material gap / answer key / judge)", lambda X: f"{X['details']['constructed_disagreements']} ({X['details']['disagreements_material_gap']} / {X['details']['disagreements_answer_key']} / {X['details']['disagreements_left_to_judge']})"),
            pair_row("A judge only: errors missed / false alarms", lambda X: f"{rate(X['combination']['A']['missed'])} / {rate(X['combination']['A']['false_alarms'])}"),
            pair_row("B rules, judge, queue: missed / false alarms / queue", lambda X: f"{rate(X['combination']['B']['missed'])} / {rate(X['combination']['B']['false_alarms'])} / {rate(X['combination']['B']['queue'])}"),
            pair_row("first judgments marked sure: wrong", lambda X: rate(X["combination"]["error_rate_sure"])),
            pair_row("first judgments marked unsure: wrong", lambda X: rate(X["combination"]["error_rate_unsure"])),
            pair_row("repeat (noise floor): verdicts changed (all)", lambda X: rate(X["perturb"]["noise_floor"])),
            pair_row("reworded rubric: verdicts changed (all)", lambda X: rate(X["perturb"]["r1"]["flip"])),
            pair_row("assurance sentence: verdicts changed (all)", lambda X: rate(X["perturb"]["assertive"]["flip"])),
            pair_row("terse rubric: verdicts changed (suggest)", lambda X: rate(X["perturb"]["r2"]["by_family"]["suggest"]["flip"])),
            pair_row("terse rubric: verdicts changed (all)", lambda X: rate(X["perturb"]["r2"]["flip"])),
            pair_row("pairs: same pick both orders (suggest)", lambda X: rate(X["pairs_lists"]["pairs"]["by_family"]["suggest"]["consistent"])),
            pair_row("second judge, suggest: claude-haiku-5-5 / claude-sonnet-5-5 right", lambda X: f"{rate(X['second_judge']['by_family']['suggest']['haiku_right'])} / {rate(X['second_judge']['by_family']['suggest']['sonnet_right'])}"),
        ]
        dv = S.get("dev_c1", {})
        if dv:
            for v, t in dv["table"].items():
                f = t["families"]["suggest"]
                rows.append([f"dev {v}: suggest pass / fail recall; score", f"{pct(R['dev']['table'][v]['families']['suggest']['pass_recall']['rate'])} / {pct(R['dev']['table'][v]['families']['suggest']['fail_recall']['rate'])}; {num(R['dev']['table'][v]['score'])}",
                             f"{pct(f['pass_recall']['rate'])} / {pct(f['fail_recall']['rate'])}; {num(t['score'])}"])
            rows.append(["adoption rule picks", R["dev"]["version"], dv["version"]])
        for k, v in S["predictions"].items():
            rv = R["predictions"].get(k, {}).get("held")
            if rv is not None and rv != v["held"]:
                rows.append([f"prediction {k}: {v['prediction']}", "held" if rv else "not held", "held" if v["held"] else "not held"])
        D1 = S.get("details", {})
        if "suggest_perturb_flips_by_item" in D1:
            fl = D1["suggest_perturb_flips_by_item"]
            rows.append(["suggest items whose verdict changed under any change (item: changes)", "", "; ".join(f"{i}: {', '.join(sorted(c))}" for i, c in sorted(fl.items()))])
        rows.append(["correction 1 runs: calls, USD", "", f"{D1.get('correction_c1_calls', 0)}, {D1.get('correction_c1_usd', 0):.4f}"])
        L += ["## Correction 1: the suggest items with the listing\n",
              "The registered suggest items lacked the listing's own sentence for each selling point and the rest of the listing (change log, correction 1). The suggest family was judged again in every stage with them added; registered answers are kept. Numbers as registered and after the correction:\n",
              table(["Measure", "As registered", "After correction 1"], rows), ""]
    rows = [[k, v["prediction"], "held" if v["held"] else "not held"] for k, v in S["predictions"].items()]
    L += ["## Predictions\n", table(["#", "Prediction", "Result"], rows), ""]
    rows = [[k, v["calls"], v["input_tokens"], v["output_tokens"], f"{v['cost_usd']:.4f}"] for k, v in S["cost"].items() if isinstance(v, dict)]
    L += ["## Cost (batch price where batched)\n", table(["Stage", "Calls", "Input tokens", "Output tokens", "USD"], rows), "", f"Total: {S['cost']['total_usd']:.4f} USD.\n"]
    D = S.get("details", {})
    if D:
        ss = D.get("source_stats", {})
        u = D["judge_usd_per_1000"]
        lines = [
            f"- Constructed-answer disagreements: {D['constructed_disagreements']}; tracing to missing item material: {D['disagreements_material_gap']}; tracing to the answer key: {D['disagreements_answer_key']}; left to the judge: {D['disagreements_left_to_judge']}.",
            f"- Argued wrong-decision reviews passed: {D['argued_wrong_decision_passed']}, of them first judgment unsure: {D['argued_wrong_decision_passed_first_unsure']}; swapped clauses passed: {D['swapped_clause_passed']}; right reviews of trap ads failed: {D['right_review_of_trap_ad_failed']}.",
            f"- Regulator misses: {D['regulator_misses']}, of them evidence-dependent: {D['regulator_misses_evidence_dependent']}.",
            f"- Judge's Verdict items with median 0.5: {D['jv_median_half_items']}; judge gave 0.5 to: {D['jv_median_half_judge_half']}.",
            f"- Terse rubric: good suggestions failed {D['terse_rubric_good_suggestions_failed']}, of them with an empty rewrite field {D['terse_rubric_good_failed_empty_rewrite']}; bad suggestions passed {D['terse_rubric_bad_suggestions_passed']}.",
            f"- Queue: C queued {D['combination_extra_queue_C_over_B']} more items than B; review items in B's queue: {D['combination_queue_B_review']}.",
            f"- Rule checks on the source projects' stored answers: {ss.get('review', {}).get('flagged_by_rules')} of {ss.get('review', {}).get('stored_right_reviews')} right reviews flagged; {ss.get('claim', {}).get('flagged_by_rules')} of {ss.get('claim', {}).get('right_verdicts')} right resume verdicts flagged.",
            f"- Judge price per 1,000 judgments (batch): review {u['review']:.3f} USD, claim {u['claim']:.3f} USD, suggest {u['suggest']:.3f} USD.",
            f"- Total calls: {D['total_calls']:,}; spent before the second judge: {D['spend_before_second_judge_usd']:.2f} USD; second judge with its estimate: {D['second_judge_calls_with_estimate']} calls, {D['second_judge_usd_with_estimate']:.4f} USD; correction 1 runs: {D.get('correction_c1_calls', 0)} calls, {D.get('correction_c1_usd', 0):.4f} USD.",
        ]
        lines.append(f"- Total spent: {S['cost']['total_usd']:.2f} USD, the correction runs included.")
        if "qc_false_flags_by_problem" in D:
            lines.append(f"- QC agent false flags by problem named: " + ", ".join(f"{k} {v}" for k, v in sorted(D["qc_false_flags_by_problem"].items())) + f"; records settled by the script: {D['qc_records_settled_by_script']}.")
        if "second_judge_usd_per_1000" in D:
            lines.append(f"- Second judge on its 120 items: {D['second_judge_usd_per_1000']:.3f} USD per 1,000 calls against {D['second_judge_items_haiku_usd_per_1000']:.3f} for claude-haiku-5-5 on the same items, {D['second_judge_price_ratio']:.0f} times as much; clean translations called flawed: {D['second_judge_mqm_clean_called_flawed']} of {D['second_judge_mqm_clean_items']}.")
        L += ["## Details used in the text\n", *lines, ""]
    (ROOT / "eval" / "results" / "RESULTS.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("wrote eval/results/RESULTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
