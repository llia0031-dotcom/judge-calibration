# Evaluation report: how far can a model judge be trusted?

Plan: [`PREREGISTRATION.md`](PREREGISTRATION.md) (frozen before the first judging request; its change log lists every later change). Every number below is in [`results/summary.json`](results/summary.json) and every table in [`results/RESULTS.md`](results/RESULTS.md); both are rebuilt from the stored answers by `python run_all.py --offline`. Intervals are 95%: Wilson for proportions, a bootstrap over clusters (all items about the same ad, resume, selling point or article together) for kappas and correlations.

## Summary

The judge is claude-haiku-5-5 with a written rubric, effort medium. It was measured against three kinds of reference, kept apart.

| Reference | Items | What the judge achieved |
|---|---|---|
| Answers fixed when the item was written (ad reviews, resume verdicts, listing suggestions) | 711 | 699 of 711 verdicts agree (98.3%, kappa 0.966); 385 of 390 planted errors caught |
| Decisions of regulators and courts (UK ASA, Chinese regulators and courts) | 46 | 39 of 46 agree (84.8%); 33 of 35 where the decision can be read off the ad, 6 of 11 where it turned on evidence the ad does not show |
| Human ratings published with datasets | 200, 480 and 240 | close to the annotators on a coarse scale (Judge's Verdict), moderate on summary quality (SummEval, Spearman 0.408 to 0.682), weak on translation error severity (WMT MQM, weighted kappa 0.290) |

What follows from it:

- **Scripts first.** Every error a script can find for certain (a quote that is not verbatim, a figure not in the quote, an unknown clause id, a malformed record) was also caught by the judge, 145 of 145, but the script catches them for nothing and with certainty. On the stored answers of the source projects, the script flagged 1 of 376 substantively right reviews and 3 of 103 right resume verdicts.
- **A judge can be left with clear-cut objective errors** (a wrong decision, a wrong clause, a misread resume, an invented property): on every such error type it caught at least 96.3% and gave the same verdict three times out of three on at least 95.3% of items.
- **It should not be left alone with ratings where people disagree** (translation severity, coherence, fluency and relevance of summaries, partly right answers) **or with decisions that turn on evidence outside the item.**
- **Rules, then one judgment, then a queue for what the judge marks unsure** missed 2 of 390 errors with 6.9% of items queued, against 7 of 390 for the judge alone, and cost less (0.243 against 0.303 USD per 1,000 items) because the script settles some items without a call.
- **The judge's "unsure" is informative**: its first judgments marked sure were wrong 0.8% of the time, those marked unsure 22.4%.
- **It was hard to push off course**: adding a long content-free passage or a sentence of assurance to a candidate changed no verdict out of 368; swapping the order of the answer options changed 2; a terse rubric changed 7 of 100 listing suggestions.
- **A quality-check agent with two tools** (is this span in the ad? what does this clause say?) caught all 119 planted errors in 239 annotation records and flagged 6 of the 120 correct ones, for 0.52 USD per 1,000 records. The acceptance standard built on it accepted 13.6% of batches with a 10% error rate, short of the target of at most 10%.
- 5 of the 12 constructed-answer disagreements trace to the answer key, not the judge (section 3.4).

## 1. What was measured

**The judge.** `claude-haiku-5-5`, effort `medium`, structured JSON output, Message Batches; one item per request unless a section says otherwise; three judgments per test item.

**The items.** Built by [`build_items.py`](build_items.py) and [`qc.py`](qc.py); sources and licences in [`../data/items/LICENSES.md`](../data/items/LICENSES.md).

| Family | Reference | Candidate | Test items |
|---|---|---|---|
| review | constructed | an ad review (decision, violations, quotes) of a Grounded Review test ad; 266 of the items show the ad image | 469 |
| claim | constructed | a "requirement met" verdict on a synthetic resume (Evidence Screening) | 142 |
| suggest | constructed | a listing-rewrite suggestion (Sellpoint Check calibration pairs) | 100 |
| regulator | regulator | an ad described in a UK ASA ruling or a Chinese regulator or court case | 46 |
| jv | human | a RAG answer scored 0 / 0.5 / 1 by three annotators (Judge's Verdict) | 200 |
| summeval | human | a news summary scored 1–5 by three experts on four dimensions (SummEval) | 480 |
| mqm | human | a Chinese-to-English translation with professional MQM error annotation (WMT 2022) | 240 |
| qc | constructed | an annotation record (decision, category, clause, span) for the quality-check agent | 239 |

In the three constructed families, right candidates are stored answers of the source projects that match their answer keys in full and pass the rule checks, and the suggestion pairs written as good; wrong candidates are the published misreadings, the suggestion pairs written as bad, and errors planted by stated rules (a swapped clause, an altered quote, a figure moved by one, a quote from another resume, a malformed structure). One more kind of wrong review argues for the opposite decision; these were written by `gen_flips.py` with the same model as the judge and kept only if they pass every rule check, so that only reading can show they are wrong. No rating in this study was produced for it by people.

**Development and test.** 195 development items (review, claim and suggest) were used only to choose the judge prompt; everything reported below is on the test items.

## 2. Choosing the judge prompt

Four versions were written before any run ([`../judgecal/prompts.py`](../judgecal/prompts.py)): v1 the bare question; v2 the written rubric with a reason and a sure / unsure flag; v3 the rubric as separate yes / no checks with the verdict computed by code; v4 v3 with three cautions (compare quotes character by character; length and assurances are not evidence; credit only what is in the material). The preregistered rule adopts a later version only if it raises the mean balanced accuracy over the three families by at least 0.02 without lowering any family's pass or fail recall by more than 0.05 and costs at most 1.5 times as much.

| Version | Score (mean balanced accuracy) | review pass / fail recall | claim | suggest | USD per 1,000 calls | Decision |
|---|---|---|---|---|---|---|
| v1 | 0.860 | 100.0% / 66.1% | 100.0% / 83.3% | 72.2% / 94.4% | 0.219 | — |
| v2 | 0.976 | 100.0% / 96.6% | 100.0% / 100.0% | 88.9% / 100.0% | 0.263 | adopted |
| v3 | 0.976 | 100.0% / 96.6% | 100.0% / 100.0% | 88.9% / 100.0% | 0.299 | not adopted: no gain |
| v4 | 0.955 | 92.9% / 96.6% | 100.0% / 100.0% | 83.3% / 100.0% | 0.316 | not adopted: no gain, and review pass recall fell by 0.071 |

The rubric is what matters: without it (v1) the judge caught only 66.1% of the wrong reviews on the development split. Splitting the rubric into checks (v3) gave the same answers at a higher price. The cautions of v4 made the judge stricter than the rubric: it failed right reviews and right suggestions it had passed before. No v5 was written.

On the test split v1 ran once beside v2. v1 caught 75.6% of the wrong reviews, 62.9% of the wrong resume verdicts and 96.0% of the wrong suggestions; v2 (first judgment) 97.4%, 100.0% and 100.0%.

## 3. Agreement with constructed answers

### 3.1 Overall

| Family | Items | Agreement | Cohen's kappa | AC1 | Errors caught | Right ones passed | Three judgments identical |
|---|---|---|---|---|---|---|---|
| review | 469 | 460/469 (98.1%; 96.4%–99.0%) | 0.961 (0.934–0.983) | 0.962 | 265/270 (98.1%) | 195/199 (98.0%) | 455/469 (97.0%) |
| claim | 142 | 142/142 (100.0%; 97.4%–100.0%) | 1.000 | 1.000 | 70/70 (100.0%) | 72/72 (100.0%) | 142/142 (100.0%) |
| suggest | 100 | 97/100 (97.0%; 91.5%–99.0%) | 0.940 (0.870–1.000) | 0.940 | 50/50 (100.0%) | 47/50 (94.0%) | 99/100 (99.0%) |
| all | 711 | 699/711 (98.3%; 97.1%–99.0%) | 0.966 (0.945–0.983) | 0.967 | 385/390 (98.7%) | 314/321 (97.8%) | 696/711 (97.9%) |

Fleiss' kappa over the three judgments: 0.959 (review), 1.000 (claim), 0.987 (suggest).

### 3.2 By error type

| Family | Type | Items | Judged right |
|---|---|---|---|
| review | wrong decision, argued | 107 | 103/107 (96.3%; 90.8%–98.5%) |
| review | swapped clause | 66 | 65/66 (98.5%) |
| review | altered quote (rule-checkable) | 57 | 57/57 (100.0%) |
| review | malformed structure (rule-checkable) | 40 | 40/40 (100.0%) |
| review | right review | 199 | 195/199 (98.0%) |
| claim | misreading of real resume text | 22 | 22/22 (100.0%) |
| claim | figure, quote, quote from another resume (rule-checkable) | 48 | 48/48 (100.0%; 92.6%–100.0%) |
| claim | right verdict | 72 | 72/72 (100.0%) |
| suggest | contradicts, invents, drops what buyers confirmed, reads silence as proof, vague | 50 | 50/50 (100.0%) |
| suggest | good suggestion | 50 | 47/50 (94.0%) |

The hardest wrong candidates were reviews that argued, carefully and with verbatim quotes, for the wrong decision: 4 of 107 passed. In three of the four the judge's first judgment was marked unsure.

### 3.3 By language and modality

Review items: English 217 of 224 right (96.9%), Chinese 243 of 245 (99.2%); image ads 263 of 266 (98.9%), text ads 197 of 203 (97.0%). The image items carry the picture and the words in it; the judge did not do worse with images.

### 3.4 Disagreements that trace to the answer key

All 12 disagreements were read, and the five below were tested with a string check ([`key_issues.py`](key_issues.py), [`results/key_issues.json`](results/key_issues.json)). No score was changed.

- Three "good" listing suggestions contain a property found in neither the listing nor the reviews (a pH of 5.5; food made to order, 现做; a "lightweight" serum). The rubric counts that as invention, and the judge failed all three on that ground.
- Two stored reviews of alcohol ads match the answer key's category and clause but add a violation about something the ad leaves out (no alcohol strength statement), which the key does not list. The judge failed them for that extra violation.

The other seven are the judge's: four argued wrong-decision reviews passed, one swapped clause passed, and two right reviews of trap ads failed (in one the judge read triangle icons in the image as fake play buttons).

## 4. Agreement with regulators and courts

| Group | Ads | Agreement | Breaches found | Cleared ads cleared |
|---|---|---|---|---|
| all | 46 | 39/46 (84.8%; 71.8%–92.4%) | 31/35 (88.6%) | 8/11 (72.7%) |
| UK ASA | 30 | 26/30 (86.7%) | 20/23 | 6/7 |
| China | 16 | 13/16 (81.2%) | 11/12 | 2/4 |
| decision readable from the ad | 35 | 33/35 (94.3%; 81.4%–98.4%) | 27/28 | 6/7 |
| decision turned on evidence the ad does not show | 11 | 6/11 (54.5%; 28.0%–78.7%) | 4/7 | 2/4 |

Kappa 0.594 (0.284–0.843), AC1 0.757. The judge marked 24 of its 46 first judgments unsure, far more than on any constructed family, and five of the seven misses are in the evidence-dependent group: whether a statistic was substantiated, or whether a "No. 1" claim rested on real sales data, cannot be decided from the ad. The two others are a darts-themed alcohol poster the ASA found irresponsible and a Chinese air-conditioner slogan ("完美变频") the regulator did not treat as an absolute claim. The set is small; the interval on the kappa is wide.

## 5. Agreement with published human ratings

### 5.1 Judge's Verdict (RAG answers, 0 / 0.5 / 1, three annotators)

| Measure | Value |
|---|---|
| Judge vs the annotators' median, exact | 147/200 (73.5%; 67.0%–79.1%) |
| Judge vs median, quadratic-weighted kappa | 0.796 (0.725–0.856) |
| Annotator vs annotator, exact (three pairs) | 62.5% to 67.5% |
| Judge vs each annotator, exact (mean of three) | 67.3% |
| Annotator vs annotator, weighted kappa | 0.450 to 0.606 |
| Judge vs each annotator, weighted kappa (mean) | 0.686 |
| Three judgments identical | 181/200 (90.5%) |

The judge agrees with each annotator about as often as the annotators agree with each other, and on the weighted kappa more closely than any two annotators do. Where the three annotators gave the same score (97 items) the judge matched it on 88 (90.7%); where they split (103 items) on 59 (57.3%). Partly right answers are the weak point: of 22 items whose median is 0.5, the judge gave 0.5 to 9.

### 5.2 SummEval (news summaries, 1–5, three experts)

| Dimension | Spearman, judge vs experts | Kendall | Expert ceiling | Judge / expert mean score |
|---|---|---|---|---|
| coherence | 0.536 (0.397–0.652) | 0.420 | 0.720 | 2.16 / 3.45 |
| consistency | 0.682 (0.541–0.801) | 0.633 | 0.633 | 4.42 / 4.74 |
| fluency | 0.408 (0.235–0.553) | 0.357 | 0.588 | 2.19 / 4.68 |
| relevance | 0.463 (0.333–0.572) | 0.360 | 0.514 | 3.06 / 3.87 |

The expert ceiling is the Spearman correlation of one expert with the mean of the other two, averaged over the three experts. The judge ranks summaries by factual consistency as well as an expert does, but falls short on coherence, fluency and relevance, and it is much harsher than the experts on fluency (mean 2.19 against 4.68): it scores the lowercase, tokenised text of these system summaries as badly written. The crowd ratings published with SummEval correlate with the experts at −0.106 to 0.054 on these items, which is why the experts are the reference here. The judge is very repeatable on this family (at least 119 of 120 items per dimension within one point across three judgments), so its errors are systematic, not noise.

### 5.3 WMT MQM, Chinese to English

| Measure | Value |
|---|---|
| Exact (none / minor / major) | 105/240 (43.8%; 37.6%–50.1%) |
| Weighted kappa | 0.290 (0.170–0.400) |
| Recall: none | 26/80 (32.5%) |
| Recall: minor | 50/80 (62.5%) |
| Recall: major | 29/80 (36.2%) |
| Any error found (minor or major) | 129/160 (80.6%) |
| Three judgments identical | 188/240 (78.3%) |

The judge finds that something is wrong in four of five flawed translations, but cannot place the severity where the professional annotators did: it called 49 of the 80 clean translations minor and 39 of the 80 major ones minor. By domain the weighted kappa ranges from 0.145 (e-commerce) to 0.471 (social media).

## 6. What can be left to whom

The preregistered thresholds (section 7.5 of the plan): a dimension is judge-reliable if agreement is high (errors caught and right ones passed at least 0.85; weighted kappa or Spearman at least 0.6; regulator agreement at least 0.85) and the three judgments are identical on at least 90% of items.

| Group | Dimensions |
|---|---|
| rule-checkable: give to a script | altered or foreign quotes, figures not in the quote, unknown clause ids, malformed structure |
| judge-reliable | wrong decision, swapped clause, misread resume, the five suggestion faults, right candidates of all three constructed families; regulator decisions readable from the ad; Judge's Verdict items where annotators agree; SummEval consistency |
| needs people | regulator decisions that turn on outside evidence; Judge's Verdict items where annotators split (weighted kappa 0.599); SummEval coherence, fluency and relevance; translation severity in all four MQM domains |

The line falls between errors with a fact behind them (the quote is there or not, the clause applies or not) and ratings where the reference itself is a matter of degree or of people disagreeing.

## 7. Rules, a judge and a review queue

On the 711 constructed test items. A: one judgment, final. B: an item failing the rule checks is failed without a call; the rest get one judgment; one marked unsure goes to the queue. C: as B with two judgments; unsure in either, or a split, goes to the queue. Queued items count as resolved correctly, the best a reviewer can do.

| Arm | Decided automatically | Errors missed | False alarms | Queue | Judge calls | USD per 1,000 items |
|---|---|---|---|---|---|---|
| A judge only | 711/711 (100.0%) | 7/390 (1.8%; 0.9%–3.7%) | 9/321 (2.8%) | 0 | 711 | 0.303 |
| B rules, judge, queue | 662/711 (93.1%) | 2/390 (0.5%; 0.1%–1.9%) | 3/321 (0.9%) | 49/711 (6.9%) | 566 | 0.243 |
| C rules, two judgments, queue | 644/711 (90.6%) | 2/390 (0.5%) | 2/321 (0.6%) | 67/711 (9.4%) | 1,132 | 0.487 |

B is better than A on every count, including cost. A second judgment (C) adds 18 queued items and doubles the calls for one false alarm fewer. The queue works because the judge's own flag is a good signal: first judgments marked sure were wrong on 5 of 662 items (0.8%), those marked unsure on 11 of 49 (22.4%). Nearly all of B's queue is review items (46 of 49).

## 8. Sensitivity

The adopted prompt was rerun once under each change on a fixed subsample of 368 test items (all claim and suggest test items, the review items of one ad in four). The noise floor is how often the first two ordinary judgments differ.

| Change | Verdicts changed | Accuracy before → after | McNemar p | Wrong candidates passed before → after |
|---|---|---|---|---|
| none (second judgment): noise floor | 3/368 (0.8%) | | | |
| rubric reworded, criteria in another order | 2/368 (0.5%) | 98.4% → 97.8% | 0.500 | 0.5% → 1.0% |
| rubric terse | 7/368 (1.9%) | 98.4% → 96.5% | 0.016 | 0.5% → 1.0% |
| answer options in the other order | 2/368 (0.5%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.0% |
| long content-free passage added to the candidate | 0/368 (0.0%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.5% |
| one sentence of assurance added to the candidate | 0/368 (0.0%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.5% |
| effort low | 5/368 (1.4%) | 98.4% → 98.6% | 1.000 | 0.5% → 0.0% |

- Rewording the rubric with all its content kept changed no more than repeating it. Cutting it down to a terse list did change verdicts, all seven on listing suggestions (7 of 100). Six were good suggestions now failed, all six with an empty rewrite field because they advise removing the claim or showing proof: the full rubric says a concrete removal or a thing to test is actionable, the terse "Concrete enough for the seller to act on?" does not say so. One bad suggestion now passed. The definitions in a rubric do work; the order and wording around them matter less.
- Length and confident tone did not move this judge on these items: not one verdict changed when a candidate was padded with a long account of how carefully it was prepared or with "I have double-checked every point".
- Effort low cost 0.182 USD per 1,000 calls against 0.212 for the same items at medium, with no loss of accuracy here.

## 9. Position and order

**Pairs.** For each test ad with a right and a wrong review, and for each suggestion pair, both were shown side by side in both orders (157 pairs, 314 requests). The judge picked the right one 152 times when it was shown first and 153 times when shown second (McNemar p = 1.000), and the same candidate in both orders in 154 of 157 pairs (98.1%). Of the three inconsistent pairs, one went to A both times and two to B, so there is no sign of a position bias. Side by side, the judge was right on more pairs (about 97%) than when it judged the two candidates one at a time (both right on 144 of 157, 91.7%).

**Lists.** All test verdicts about one resume went into one request, in a fixed order and reversed (16 resumes, 142 verdicts). 139 of the 142 verdicts were the same in both orders; accuracy was 140 of 142 in lists against 142 of 142 one at a time.

## 10. The quality-check agent and an acceptance standard

Each test ad gave two annotation records: its answer key, and a copy with one planted error (approve and reject swapped; another category and clause; a span that exists in the ad but is not what breaks it; a span altered so it is no longer verbatim; a clause id not in the library). The agent saw one record, the ad and an index of the clause library, and had two tools: `check_span` (is this span verbatim in the ad?) and `get_clause` (the text of a clause). Tool rounds of all open records went out as one batch each.

| Check | Wrong records caught | Correct records flagged | decision | category | span, wrong words | span, not verbatim | unknown clause |
|---|---|---|---|---|---|---|---|
| script only | 18/119 (15.1%) | 0/120 (0.0%) | 0/65 | 0/22 | 0/14 | 10/10 | 8/8 |
| agent only | 119/119 (100.0%; 96.9%–100.0%) | 6/120 (5.0%; 2.3%–10.5%) | 65/65 | 22/22 | 14/14 | 10/10 | 8/8 |
| script, then agent | 119/119 (100.0%) | 6/120 (5.0%) | 65/65 | 22/22 | 14/14 | 10/10 | 8/8 |

The agent made 2.88 tool calls per record (every record had at least one) and named the right problem for 114 of the 119 errors it caught. It cost 0.52 USD per 1,000 records alone and 0.48 after the script, which settles the records it can. Of the six correct records it flagged, three were for describing a picture-only violation instead of quoting words, which the record format allows, and three for a violation the record does not list. One of those (`qc-zh-t08-key`) is a health-food ad without the statement 「本品不能代替药物」 that clause CN-AL-18 requires, which the answer key does not list ([`results/key_issues.json`](results/key_issues.json)).

**Acceptance standard** for a delivered batch of 100 records, fixed in advance: S1 at most 2% fail the script checks; S2 at most 10% of the rest are flagged by the agent; S3 of 20 unflagged records drawn at random, at most one is wrong on review. Simulated with 2,000 batches per error rate from the agent's stored verdicts (in S3 the answer key stands in for the reviewer):

| True error rate | 0% | 1% | 2% | 5% | 10% | 20% |
|---|---|---|---|---|---|---|
| Batches accepted | 99.1% | 96.2% | 91.5% | 62.0% | 13.6% | 0.1% |

The first target (accept at least 90% of batches at 2% errors or fewer) was met; the second (accept at most 10% at 10% errors or more) was not: 13.6% of batches with 10% errors passed. S3 never decided anything, because the agent left no wrong record unflagged; every rejection came from S1 or S2. Post hoc, and not a result: on these records no single flag-rate threshold between 6% and 10% meets both targets, because the agent's false flags (5% of correct records) blur the flag rate. A version of S2 that counts only flags confirmed on review would separate the two cases; it was not tested.

## 11. A second judge

The plan allowed one comparison if the total spent was still at most 3.6 USD (it was 2.21). claude-sonnet-5-5 judged 120 test items once (40 each of claim, suggest and mqm, chosen by hash), with the same prompts and effort; five live calls estimated the cost first.

| Family | Items | claude-haiku-5-5 right (first judgment) | claude-sonnet-5-5 right | Same verdict | McNemar p |
|---|---|---|---|---|---|
| claim | 40 | 40/40 (100.0%) | 40/40 (100.0%) | 40/40 | 1.000 |
| suggest | 40 | 40/40 (100.0%) | 39/40 (97.5%) | 39/40 | 1.000 |
| mqm | 40 | 18/40 (45.0%; 30.7%–60.2%) | 21/40 (52.5%; 37.5%–67.1%) | 29/40 | 0.508 |

On the same items claude-sonnet-5-5 cost 1.483 USD per 1,000 calls against 0.114 for claude-haiku-5-5, 13 times as much. On the constructed families both are at the ceiling; the one suggestion the larger model failed is a good one that presumes a test report the material does not mention. On translation severity it was right three more times out of 40, not a significant difference, and it too called most clean translations flawed (8 of 9 here). A larger judge does not fix what section 6 puts in the "needs people" group; on these items it buys little.

## 12. Predictions

| # | Prediction | Result |
|---|---|---|
| 1 | The judge alone catches less than 95% of rule-checkable errors | not held: it caught 145 of 145 |
| 2 | Agreement with regulators is lower than with constructed answers | held: 84.8% against 98.3% |
| 3 | Lower on evidence-dependent regulator decisions | held: 54.5% against 94.3% |
| 4 | On Judge's Verdict, the judge's agreement with each annotator lies within the annotators' range | held: 67.3% within 62.5% to 67.5% |
| 5 | On SummEval, below the expert ceiling on all four dimensions | not held: on consistency 0.682 against 0.633 |
| 6 | Three identical judgments less often on the human-rated families | held |
| 7 | A sentence of assurance raises the pass rate of wrong candidates by at least 2 points | not held: no verdict changed |
| 8 | Rewording the rubric changes more verdicts than repeating it | not held: 0.5% and 1.9% against 0.8% (the terse rubric changed more, the reworded one fewer) |
| 9 | Same pick in both orders in at least 90% of pairs | held: 98.1% |
| 10 | Rules, judge and queue miss fewer errors than the judge alone, with a queue of at most 20% | held: 2 against 7, queue 6.9% |
| 11 | Script then agent catches at least 90% of wrong records and flags at most 10% of correct ones | held: 100.0% and 5.0% |
| 12 | The acceptance standard meets both targets | not held: 13.6% accepted at 10% errors |

## 13. Cost

All calls at batch price, except the 40 pilot calls, the 13 mechanics-check calls, the 5 cost-estimate calls and the last 13 agent turns, which went out as ordinary calls.

| Stage | Calls | USD |
|---|---|---|
| pilot (request check, not scored) | 40 | 0.0153 |
| quality-check agent, mechanics check (not scored) | 13 | 0.0049 |
| argued wrong-decision reviews, written once | 288 | 0.1546 |
| dev: four prompt versions | 780 | 0.2140 |
| main: three judgments per test item, v1 once | 5,742 | 1.1257 |
| perturb: six changes on 368 items | 2,208 | 0.4613 |
| pair | 314 | 0.0939 |
| list | 32 | 0.0156 |
| quality-check agent (239 records, 491 turns) | 491 | 0.1242 |
| second judge: estimate and run | 125 | 0.1931 |
| total | 10,033 | 2.4026 |

The judge's own price, per 1,000 judgments at batch price: 0.400 USD for an ad review (the clause library is in every request), 0.121 for a resume verdict, 0.109 for a listing suggestion.

## 14. Limits

- **One judge model, one sitting.** Other models, other days and other effort levels may differ; section 11 compares one more model on 120 items.
- **The constructed items are as good as the rules that made them.** Section 3.4 shows five places where the answer key is the weaker side. The planted errors are of a few kinds; real reviews go wrong in more ways.
- **The argued wrong-decision reviews were written by the same model as the judge.** A judge may find its own model's arguments easier or harder to see through than other writers'.
- **Small groups.** 46 regulator ads, 11 of them evidence-dependent; 4 to 22 items in some error types. The intervals show it.
- **Near the ceiling on two families.** The judge got every resume verdict right; those items can no longer separate prompts or models.
- **The queue is counted as resolved correctly.** That is the best case for a reviewer, not a measurement of one.
- **No ratings were produced for this study.** The human references are the datasets' own: one data file (Judge's Verdict, technical support answers), one benchmark of 2020-era summarisers (SummEval) and one year of WMT (MQM).
- **Texts not redistributed** (regulator ads, SummEval articles, TikTok policy text) are kept out of the public copy; their stored judgments rescore offline, but a full rerun needs the originals.
