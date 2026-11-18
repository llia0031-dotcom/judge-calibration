# Pre-registration: how far can a model judge be trusted?

Written 2026-11-18, before any judging request of the evaluation was sent. The only model calls made before this file were a 40-call pilot that checked the requests work and measured tokens per call (`eval/results/raw/pilot.jsonl`, not scored), a 13-call mechanics check of the quality-check agent on development records (`qc-pilot.jsonl`, not scored), and the one-time generation of the "argued for the wrong decision" reviews (`eval/gen_flips.py`), which are test material, not judgments. The files this plan freezes are listed with their hashes at the end. Every change made after this point is written in the change log at the bottom, with the date and the reason, before the changed part is run.

## 1. Question

A model judge ("is this answer right?", "score this from 1 to 5") is used in many evaluation pipelines. This study measures one such judge against three kinds of reference, kept apart:

| Reference | What the answer is | Families |
|---|---|---|
| constructed | the answer was fixed when the item was written, or the error was planted by a stated rule | review, claim, suggest, qc |
| regulator | a published decision of a regulator or a court | regulator |
| human | a human rating that ships with a public dataset | jv, summeval, mqm |

No rating in this study was produced for it by people. "Human" always means ratings already published with a dataset.

## 2. The judge

`claude-haiku-5-5`, effort `medium`, structured JSON output, Message Batches. Each item is judged in its own request unless a stage says otherwise.

## 3. Items

Built by `eval/build_items.py` (and `eval/qc.py build`) from the sources below. 1,872 judging items and 287 annotation records.

| Family | Source | Candidate judged | Right / wrong | Dev | Test |
|---|---|---|---|---|---|
| review | Grounded Review test ads (text and image, Chinese and English, MIT) | an ad review: decision, violations, quotes | right: stored reviews that match the answer key in full and pass the rule checks (at most two per ad). wrong: the opposite decision argued (generated), a swapped clause, an altered ad quote, a malformed structure | 101 | 469 |
| claim | Evidence Screening synthetic resumes (MIT) | a "requirement met" verdict with fact and quotes | right: stored verdicts that match the answer key and pass the quote check. wrong: the 40 published misreadings; 20 each of a figure moved by one, a quote altered by one character, a quote from another resume | 58 | 142 |
| suggest | Sellpoint Check calibration pairs (MIT) | a listing-rewrite suggestion | one that should pass and one that should fail per selling point, with the reason it should fail | 36 | 100 |
| regulator | 30 UK ASA rulings, 16 Chinese regulator and court cases (text not redistributed) | the ad itself: breach or not | the published decision | 0 | 46 |
| jv | Judge's Verdict, train file (CC BY-SA 4.0) | a RAG answer, scored 0 / 0.5 / 1 against a reference answer | the median of three annotators | 0 | 200 |
| summeval | SummEval expert annotations (MIT; articles not redistributed) | a news summary, 1–5 on one dimension | the mean of three experts | 0 | 480 (30 articles × 4 summaries × 4 dimensions) |
| mqm | WMT 2022 MQM, Chinese to English (Apache-2.0) | a translation: none, minor or major errors | MQM score 0 = none, > −5 = minor, ≤ −5 = major | 0 | 240 (80 per class, 20 per domain) |
| qc | Grounded Review answer keys as annotation records | one record: decision, category, clause, span | the key itself, and one copy with one planted error | 48 | 239 |

Development split: for review, the ads of the source's dev split; for claim and suggest, one resume or selling point in four, chosen by hash. Development items are used only to choose the judge prompt (section 5) and are never reported as results. All other items are test items.

## 4. Rule checks

`judgecal/rules.py` decides what a script can decide for certain: quotes not verbatim in the material (evidence-check's matcher), figures in a stated fact that the quotes do not contain, clause ids not in the library, a reject without a violation or an approve with one. A rule check never says a candidate is right. By construction of the item set, every planted error of the types quote, figure, foreign, format (and in qc: span_altered, unknown_clause) fails the rule checks, and every right candidate passes them; the report also gives how many stored right reviews and verdicts were left out because the rules flagged them.

## 5. Judge prompt versions and the adoption rule

`judgecal/prompts.py` holds v1–v4 for the three families with right and wrong candidates (review, claim, suggest):

- v1: the bare question, pass or fail.
- v2: v1 with the written rubric, a reason and a sure / unsure flag.
- v3: the rubric as separate yes / no checks; the verdict is computed from the checks by code.
- v4: v3 with three cautions (compare quotes character by character; length, tone and assurances are not evidence; credit only what is in the material).

Each version judges every development item once (`run.py dev`). For each family, pass recall is the share of right candidates judged pass and fail recall the share of wrong candidates judged fail; balanced accuracy (BA) is their mean. The score of a version is the mean BA over the three families.

Rule: the current version starts as v1. v2, v3 and v4 are compared with the current version in that order; a version replaces the current one if all four hold:

1. its score is at least 0.02 higher;
2. in no family is its fail recall more than 0.05 lower;
3. in no family is its pass recall more than 0.05 lower;
4. its mean cost per call is at most 1.5 times the current version's.

Otherwise the current version stays. At most one further version (v5) may be written after the development results are seen; it is entered in the change log before it runs and passes through the same rule. The version left at the end is "adopted" (`eval/adopted.json`). Every version's development results are reported, adopted or not. On the test split, v1 is run once beside the adopted version as the baseline.

The regulator, jv, summeval and mqm families each have one fixed prompt, written before any of their items was judged, and are never used to choose anything.

## 6. Stages

| Stage | What | Requests |
|---|---|---|
| dev | v1–v4 on the development items, once | 780 |
| main | the adopted version on every test item, three times; v1 once (review, claim, suggest); the fixed prompts three times | about 5,742 |
| perturb | the adopted version once on a fixed subsample (all claim and suggest test items, the review items of one ad in four) under each of six changes: rubric wording r1, rubric wording r2, answer options listed in the other order, a long content-free passage added to the candidate's free text, one sentence of assurance added, effort low | about 2,208 |
| pair | a right and a wrong candidate for the same material, side by side, in both orders (one pair per test ad and per suggestion pair) | 314 |
| list | all test verdicts about one resume in one request, in a fixed order and reversed | 32 |
| qc | the quality-check agent on the 239 test records, tool rounds batched | about 239 records × 2–4 rounds |

Budget: the whole project stays below 5 USD. Before each stage its cost is estimated from the pilot; a stage that would take the total above 4.5 USD is not run, and the report says so.

## 7. Measures

All proportions have 95% Wilson intervals. Kappas have 95% bootstrap intervals that resample clusters (all items about the same ad, resume, selling point, article or source sentence stay together), 2,000 resamples, seed 20261118. Small groups are reported with their counts; nothing is dropped for being small.

**7.1 Agreement with constructed answers.** The judge's verdict on an item is the majority of its three judgments. Reported per family, per dimension (error type), per language and per modality (image or text ads): agreement, Cohen's kappa, Gwet's AC1 (kappa misleads when one label dominates), fail recall ("errors caught") and false-fail rate (right candidates judged fail).

**7.2 Stability.** Share of items whose three judgments are identical; Fleiss' kappa over the three judgments.

**7.3 Agreement with regulators.** Agreement and kappa of the majority verdict with the published decision, by language and by whether the decision turned on evidence the ad does not show (`evidence_dependent`).

**7.4 Agreement with human ratings.**
- jv: the judge's score (majority of three; if all differ, the middle one) against the annotators' median: exact agreement, quadratic-weighted kappa. Human ceiling: mean pairwise exact agreement and weighted kappa between the three annotators; the judge's mean pairwise agreement with each annotator is compared with it.
- summeval: per dimension, Spearman and Kendall correlation between the judge's mean score (three judgments) and the experts' mean, over items. Human ceiling: for each expert, the Spearman correlation with the mean of the other two, averaged over experts.
- mqm: exact agreement on the three classes, quadratic-weighted kappa (none < minor < major), recall per class, and recall of "any error" (minor or major) against none.

**7.5 Objective errors and subjective preferences.** Each dimension is put in one of three groups by these thresholds, fixed now:
- rule-checkable: the planted error types that fail the rule checks (section 4);
- judge-reliable: any other dimension where the judge's agreement with the reference is high (fail recall ≥ 0.85 for planted errors and pass recall ≥ 0.85 for right candidates; weighted kappa or Spearman ≥ 0.6 for ratings; agreement ≥ 0.85 for regulator decisions) and its three judgments are identical on at least 90% of items (for summeval: max − min ≤ 1);
- needs people: everything else.

**7.6 Rules, judge and a review queue together.** Computed from the main-stage judgments of the test items of review, claim and suggest:
- A, judge only: one judgment (the first) per item; its verdict is final.
- B, rules then judge: an item failing the rule checks is fail without a judge call; the others get one judgment; a judgment marked unsure goes to the review queue.
- C, rules then two judgments: as B, but two judgments; the item goes to the queue if either is unsure or they disagree.

Reported for each: automatic coverage (share decided without the queue), errors missed (wrong candidates that end as pass without the queue), false alarms (right candidates that end as fail without the queue), queue size, model calls and cost. Items in the queue are counted as resolved correctly, which is the best a reviewer can do; the queue size is the price of that. B and C are compared with A.

**7.7 Sensitivity.** For each perturbation: the share of items whose verdict differs from the first main judgment, beside the share that differs between the first and second main judgments (the noise floor); the change in accuracy with an exact McNemar test. For the long passage and the assurance: the change in the pass rate of wrong candidates (does content-free text make a wrong answer pass?) and of right ones. For effort low: accuracy and cost per call.

**7.8 Position and order.** Pairs: accuracy with the right candidate shown first and second; the share of pairs where the judge picks the same candidate in both orders. Lists: agreement of each verdict between the two orders, and accuracy in lists compared with one item per request.

**7.9 Quality-check agent and an acceptance standard.** Three ways to check the 239 test records: script only (rule checks), agent only, and script then agent (the agent only sees what the script passes). For each: wrong records caught (overall and per error type), correct records flagged, cost per record.

Acceptance standard for a delivered batch of N = 100 records, fixed now:
- S1: at most 2% of the records fail the script checks (these records are returned whatever the outcome);
- S2: at most 10% of the remaining records are flagged by the agent;
- S3: of 20 records drawn at random from the unflagged ones, at most 1 is wrong on review.

A batch is accepted when S1, S2 and S3 all hold. Its operating characteristic is simulated: for true error rates 0, 1, 2, 5, 10 and 20%, 2,000 batches each, records drawn with replacement from the test records (wrong ones from the wrong records, correct ones from the correct records), with the agent's stored verdict for each record; in S3 the answer key stands in for the reviewer. Targets: accepted at least 90% of the time when the error rate is at most 2%, at most 10% of the time when it is 10% or more.

**7.10 A second judge (conditional).** If the total spent after the stages above is at most 3.6 USD, `claude-sonnet-5-5` judges 120 test items (40 each of claim, suggest and mqm, chosen by hash) once with the same prompts, after its cost is estimated from five live calls. Otherwise this is not run.

## 8. Predictions

Written now, marked held or not held in the report.

1. The judge alone catches less than 95% of the rule-checkable errors.
2. Agreement with regulator decisions is lower than agreement with constructed answers.
3. Agreement is lower on evidence-dependent regulator decisions than on the others.
4. On jv, the judge's mean pairwise agreement with the annotators lies within the range of the annotators' pairwise agreement with each other.
5. On summeval, the judge's correlation is below the expert ceiling on all four dimensions.
6. The three judgments are identical less often on the human-rated families than on the constructed ones.
7. One sentence of assurance raises the pass rate of wrong candidates by at least 2 percentage points.
8. Rewording the rubric changes more verdicts than repeating the same prompt.
9. In pairs, the judge picks the same candidate in both orders at least 90% of the time.
10. B misses fewer errors than A with a queue of at most 20% of items.
11. Script then agent catches at least 90% of the wrong records and flags at most 10% of the correct ones.
12. The acceptance standard meets both targets.

## 9. What this study does not claim

It measures one judge model on these items. The constructed items were written by the source projects and here; their answers are as good as the rules that made them. The regulator set is small (46 ads). The jv, summeval and mqm ratings are the datasets' own. Nothing here is a statement about the quality of any regulator, dataset or model provider.

## Frozen files

| File | sha256 (12) |
|---|---|
| `judgecal/llm.py` | 72b4c4bf230b |
| `judgecal/prompts.py` | b855443f74ee |
| `judgecal/rules.py` | d565e0bc2a48 |
| `judgecal/stats.py` | 605aaacb41c5 |
| `judgecal/items.py` | b44c31f91aaf |
| `eval/build_items.py` | 5aae03599351 |
| `eval/run.py` | 2adb29135e6b |
| `eval/qc.py` | e572d39ce615 |
| `eval/gen_flips.py` | 3f00c1a21ae0 |
| `data/policy/cn.json` | da118cfc57eb |
| `data/generated/review_flips.jsonl` | 2111b5691b14 |
| `data/items/review.jsonl` | f64cbb2f83b7 |
| `data/items/claim.jsonl` | a340b79327f9 |
| `data/items/suggest.jsonl` | 67d4087c77de |
| `data/items/jv.jsonl` | c54b360af400 |
| `data/items/mqm.jsonl` | 0219399a2443 |
| `data/items/qc.jsonl` | d17fd40ad514 |
| `private/items/regulator.jsonl` | 3a328cfe608c |
| `private/items/summeval.jsonl` | 67d5b28bf81b |
| `private/policy/tiktok.json` | 2ade50807744 |

## Change log

- 2026-11-18, after the dev stage: the adoption rule picked v2 (v2 over v1: score 0.976 against 0.860; v3 tied with v2 and was not adopted; v4 scored 0.955 and lowered the pass recall of review by 0.071). No v5 was written: v2 is within 0.03 of a perfect development score, so there was nothing a further version could gain that the rule would see. Nothing frozen was changed.
- 2026-11-18, before the main stage: two files were added that do not change any item, prompt or measure: `data/policy/tiktok.stub.json` (clause ids, titles and links, loaded only where the TikTok policy text is absent, as in the public copy) and `eval/source_stats.py` (counts how many substantively right stored answers the rule checks flag, section 4).
