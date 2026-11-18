# Judge Calibration

How far can a model judge be trusted? This project measures one judge (claude-haiku-5-5 grading answers against a written rubric) against three kinds of reference kept apart: answers fixed when the test item was written, decisions published by regulators and courts, and human ratings that ship with public datasets. It then works out which checks a script should do, which a judge can be left with, and which need a person, and tests a quality-check agent on annotation records with a measurable acceptance standard. Everything was preregistered before the first judging request.

[中文说明](README.zh-CN.md)

## Where this fits

This project belongs to a set of projects built on one idea: an AI should show its evidence. Several of them grade answers with a model and a rubric; this one measures that grader.

- **[Grounded Review](https://github.com/llia0031-dotcom/grounded-review)** reviews ads against ad rules and quotes the words that break them. Its test ads, answer keys and stored reviews are the largest family here, including the image ads, and its 46 regulator and court cases are the regulator reference.
- **[Evidence Screening](https://github.com/llia0031-dotcom/evidence-screening)** checks resumes against job requirements with quotes. Its "requirement met" verdicts and its 40 planted misreadings are the claim family.
- **[Sellpoint Check](https://github.com/llia0031-dotcom/sellpoint-check)** graded its listing-rewrite suggestions with a rubric after calibrating the grader on pairs of good and bad suggestions. Those pairs are the suggest family.
- **[evidence-check](https://github.com/llia0031-dotcom/evidence-check)** is the rule layer: every "is this quote verbatim, is this figure in the quote" check here is its matcher. Every number in the report is checked against `eval/results/summary.json` with it.
- **[Grounded Labelling Pipeline](https://github.com/llia0031-dotcom/grounded-labelling-pipeline)** sends uncertain calls to a review queue. Section 6 of the report measures what such a queue buys when a judge is in the loop.
- **[Evidence First](https://github.com/llia0031-dotcom/evidence-first)** collects the evaluation cards of all the projects.

## What it found

| Question | Answer |
|---|---|
| Does the judge agree with answers fixed when the items were written? | Yes, on these items: 702 of 711 verdicts (98.7%, Cohen's kappa 0.974) on ad reviews, resume verdicts and listing suggestions, 385 of 390 planted errors caught, and the same verdict three times out of three on 697 of 711. 2 of the 9 disagreements trace to the answer key, not the judge. As first run there were 12: three more came from listing-suggestion items that left out the product listing, an error in this study's items, corrected and rerun (report, section 3.5). |
| With regulators and courts? | Less: 39 of 46 published decisions (84.8%). 33 of 35 where the decision can be read off the ad, 6 of 11 where it turned on evidence the ad does not show. |
| With human ratings that ship with public datasets? | Close on a coarse scale: on Judge's Verdict it agrees with each annotator 67.3% of the time, inside the annotators' own range of 62.5% to 67.5%. Moderate on summary quality: SummEval Spearman 0.408 (fluency) to 0.682 (consistency). Weak on translation severity: WMT MQM weighted kappa 0.290. |
| What should a script check, and what a judge? | A script: quotes that are not verbatim, figures not in the quote, unknown clause ids, malformed records. The judge caught all 145 of these too, but the script costs nothing. A judge: clear-cut objective errors (wrong decision, wrong clause, misread resume, invented property), at least 96.3% caught on every such type. People: ratings where annotators disagree, and decisions that turn on outside evidence. |
| Rules, then a judge, then a queue? | Rules first, one judgment, and the judgments marked unsure to a review queue missed 2 of 390 errors with 6.9% of items queued, against 7 of 390 for the judge alone, and cost less (0.244 against 0.304 USD per 1,000 items). The judge's unsure flag is a real signal: 0.5% of its sure judgments were wrong, 20.4% of its unsure ones. |
| Can wording, order or padding push it off course? | Hardly, on these items. Padding a candidate with a long account of its own care changed none of 368 verdicts, and neither padding nor a sentence of assurance made a wrong candidate pass; swapping the answer options changed 2, as many as repeating the same prompt; rewording the rubric changed 5 and a terse rubric 4, mostly good listing suggestions near the line. In pairs it picked the same candidate in both orders 154 times out of 157. |
| Can an agent check annotation records? | With two tools (is this span in the ad? what does this clause say?) it caught all 119 planted errors in 239 records and flagged 6 of the 120 correct ones, for 0.52 USD per 1,000 records. The acceptance standard built on it accepted 91.5% of batches with 2% errors but also 13.6% with 10% errors, missing its second target. |
| Does a larger judge help? | Not here. claude-sonnet-5-5 cost 13 times as much on the same 120 items, matched claude-haiku-5-5 on resume verdicts and suggestions, and was right three more times out of 40 on translation severity (p = 0.508). |

Of 12 preregistered predictions, 8 held and 4 did not; each is listed with its result in [`eval/EVALUATION.md`](eval/EVALUATION.md). Every number above is checked against [`eval/results/RESULTS.md`](eval/results/RESULTS.md) with evidence-check (`tools/check_numbers.py`, claims in `eval/results/claims.json`). The whole project cost 2.61 USD in API calls.

## Run it

Python 3.12.

```bash
pip install -r requirements.txt
python run_all.py --offline    # rescore everything from the stored answers and run the tests (no model calls)
```

`python run_all.py` reruns every stage that is not finished yet with the Message Batches API; finished requests are never sent again. It reads the API key from the file named by `EVAL_ENV_FILE` (a line `ANTHROPIC_API_KEY=...`, see `.env.example`).

What a rerun cannot rebuild from this repository:

- the regulator ads and the SummEval articles are not redistributed, so `data/items/regulator.jsonl` and `data/items/summeval.jsonl` hold ids, answers and links only; the stored judgments on them are included and rescore offline;
- the TikTok ad policy text is not redistributed; `data/policy/tiktok.stub.json` has the clause ids, titles and links, and English policy quotes in the items are replaced by the clause id and link. Re-judging the English review items needs the policy text from those pages.

## Layout

| Folder | Contents |
|---|---|
| `judgecal/` | the judge prompts (v1–v4, three rubric wordings), the rule checks, the batch runner, the statistics |
| `eval/` | item builder, stage runner, quality-check agent, scorer, preregistration, report |
| `eval/results/` | `summary.json` (every number), `RESULTS.md` (every table), `raw/` (every stored judgment) |
| `data/items/` | the items of the seven families and the quality-check records, with their sources and licences |
| `data/images/` | the image ads (rendered, fictional brands) |
| `data/policy/` | the Chinese clause library; the TikTok clause index |
| `tests/` | offline tests |

## Third-party data and tools

| What | Used for | Licence |
|---|---|---|
| [nvidia/judges-verdict](https://huggingface.co/datasets/nvidia/judges-verdict) | human-rated RAG answers (three annotators each) | CC BY-SA 4.0; `data/items/jv.jsonl` keeps it |
| [SummEval](https://github.com/Yale-LILY/SummEval) | expert-rated summaries | MIT (annotations); articles not included |
| [WMT MQM human evaluation](https://github.com/google/wmt-mqm-human-evaluation) | professionally annotated Chinese-to-English translations | Apache-2.0 |
| [scikit-learn](https://scikit-learn.org), [statsmodels](https://www.statsmodels.org), [SciPy](https://scipy.org) | kappa, Wilson intervals, Fleiss' kappa, correlations, exact tests | BSD-3-Clause |

The methods follow published work: rubric scoring with stated criteria (G-Eval), swapping the order of pairs and the position, verbosity and self-enhancement biases (MT-Bench), checking a judge before trusting it and the drift of criteria (EvalGen), judging with tools (Agent-as-a-Judge), injected biases (CALM), and escalating uncertain calls to people (Trust or Escalate). No code was copied.

## Limits

- **One judge, one sitting.** Other models, days and settings may differ; one more model was compared on 120 items only.
- **Constructed answers are as good as the rules and material that made them.** In two places the answer key, not the judge, is the weaker side. The listing-suggestion items first left out the product listing; this was found after the run, corrected in the plan's change log and rerun, and the numbers as registered are kept beside the corrected ones. The planted errors are of a few kinds; real reviews go wrong in more ways.
- **The argued wrong-decision reviews were written by the same model as the judge**, which may make them easier or harder for it to see through.
- **Small groups.** 46 regulator decisions, 11 of them evidence-dependent; 4 to 22 items in some error types. The tables give 95% intervals.
- **At the ceiling on resume verdicts and listing suggestions.** The judge got every one right, so these families no longer separate prompts or models.
- **The review queue is counted as resolved correctly**, the best case for a reviewer, not a measurement of one.
- **No ratings were produced for this study.** The human references are the datasets' own.

## Licence

MIT, except `data/items/jv.jsonl` (CC BY-SA 4.0) and the other data files listed in `data/items/LICENSES.md`.
