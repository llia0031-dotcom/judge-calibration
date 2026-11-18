# Results (generated from summary.json)

Adopted judge prompt: v2. Intervals are 95% (Wilson for proportions, cluster bootstrap for kappas).

## 1. Prompt versions on the development split

| Version | Score (mean BA) | review pass / fail recall | claim | suggest | USD per 1,000 calls |
|---|---|---|---|---|---|
| v1 | 0.860 | 100.0% / 66.1% | 100.0% / 83.3% | 72.2% / 94.4% | 0.219 |
| v2 | 0.976 | 100.0% / 96.6% | 100.0% / 100.0% | 88.9% / 100.0% | 0.263 |
| v3 | 0.976 | 100.0% / 96.6% | 100.0% / 100.0% | 88.9% / 100.0% | 0.299 |
| v4 | 0.955 | 92.9% / 96.6% | 100.0% / 100.0% | 83.3% / 100.0% | 0.316 |

Adoption steps: v2 vs v1: adopted; v3 vs v2: not adopted (score_up_0.02); v4 vs v2: not adopted (score_up_0.02, no_pass_recall_drop_0.05)

## 2. Constructed answers (test split, majority of three judgments)

| Family | Items | Agreement | Cohen's kappa | AC1 | Errors caught | Right ones passed | Three judgments identical | Fleiss' kappa |
|---|---|---|---|---|---|---|---|---|
| review | 469 | 460/469 (98.1%; 96.4%–99.0%) | 0.961 (0.934–0.983) | 0.962 | 265/270 (98.1%; 95.7%–99.2%) | 195/199 (98.0%; 94.9%–99.2%) | 455/469 (97.0%; 95.1%–98.2%) | 0.959 |
| claim | 142 | 142/142 (100.0%; 97.4%–100.0%) | 1.000 (1.000–1.000) | 1.000 | 70/70 (100.0%; 94.8%–100.0%) | 72/72 (100.0%; 94.9%–100.0%) | 142/142 (100.0%; 97.4%–100.0%) | 1.000 |
| suggest | 100 | 97/100 (97.0%; 91.5%–99.0%) | 0.940 (0.870–1.000) | 0.940 | 50/50 (100.0%; 92.9%–100.0%) | 47/50 (94.0%; 83.8%–97.9%) | 99/100 (99.0%; 94.6%–99.8%) | 0.987 |
| all | 711 | 699/711 (98.3%; 97.1%–99.0%) | 0.966 (0.945–0.983) | 0.967 | 385/390 (98.7%; 97.0%–99.5%) | 314/321 (97.8%; 95.6%–98.9%) | 696/711 (97.9%; 96.5%–98.7%) |  |

### By error type

`correct` rows are right candidates (share passed); the others are planted errors (share caught).

| Family | Type | Items | Judged right | Identical ×3 |
|---|---|---|---|---|
| review | clause | 66 | 65/66 (98.5%; 91.9%–99.7%) | 66/66 (100.0%; 94.5%–100.0%) |
| review | correct | 199 | 195/199 (98.0%; 94.9%–99.2%) | 190/199 (95.5%; 91.6%–97.6%) |
| review | decision | 107 | 103/107 (96.3%; 90.8%–98.5%) | 102/107 (95.3%; 89.5%–98.0%) |
| review | format | 40 | 40/40 (100.0%; 91.2%–100.0%) | 40/40 (100.0%; 91.2%–100.0%) |
| review | quote | 57 | 57/57 (100.0%; 93.7%–100.0%) | 57/57 (100.0%; 93.7%–100.0%) |
| claim | correct | 72 | 72/72 (100.0%; 94.9%–100.0%) | 72/72 (100.0%; 94.9%–100.0%) |
| claim | figure | 16 | 16/16 (100.0%; 80.6%–100.0%) | 16/16 (100.0%; 80.6%–100.0%) |
| claim | foreign | 14 | 14/14 (100.0%; 78.5%–100.0%) | 14/14 (100.0%; 78.5%–100.0%) |
| claim | misreading | 22 | 22/22 (100.0%; 85.1%–100.0%) | 22/22 (100.0%; 85.1%–100.0%) |
| claim | quote | 18 | 18/18 (100.0%; 82.4%–100.0%) | 18/18 (100.0%; 82.4%–100.0%) |
| suggest | absence_as_false | 6 | 6/6 (100.0%; 61.0%–100.0%) | 6/6 (100.0%; 61.0%–100.0%) |
| suggest | contradicts | 20 | 20/20 (100.0%; 83.9%–100.0%) | 20/20 (100.0%; 83.9%–100.0%) |
| suggest | correct | 50 | 47/50 (94.0%; 83.8%–97.9%) | 49/50 (98.0%; 89.5%–99.6%) |
| suggest | drops_confirmed | 4 | 4/4 (100.0%; 51.0%–100.0%) | 4/4 (100.0%; 51.0%–100.0%) |
| suggest | invents | 9 | 9/9 (100.0%; 70.1%–100.0%) | 9/9 (100.0%; 70.1%–100.0%) |
| suggest | vague | 11 | 11/11 (100.0%; 74.1%–100.0%) | 11/11 (100.0%; 74.1%–100.0%) |

### By language and modality

| Family | Group | Items | Judged right | Pass recall | Fail recall |
|---|---|---|---|---|---|
| review | en | 224 | 217/224 (96.9%; 93.7%–98.5%) | 96.8% | 96.9% |
| review | zh | 245 | 243/245 (99.2%; 97.1%–99.8%) | 99.1% | 99.3% |
| review | image | 266 | 263/266 (98.9%; 96.7%–99.6%) | 98.2% | 99.4% |
| review | text | 203 | 197/203 (97.0%; 93.7%–98.6%) | 97.7% | 96.5% |
| claim | en | 61 | 61/61 (100.0%; 94.1%–100.0%) | 100.0% | 100.0% |
| claim | zh | 81 | 81/81 (100.0%; 95.5%–100.0%) | 100.0% | 100.0% |
| claim | text | 142 | 142/142 (100.0%; 97.4%–100.0%) | 100.0% | 100.0% |
| suggest | en | 54 | 52/54 (96.3%; 87.5%–99.0%) | 92.6% | 100.0% |
| suggest | zh | 46 | 45/46 (97.8%; 88.7%–99.6%) | 95.7% | 100.0% |
| suggest | text | 100 | 97/100 (97.0%; 91.5%–99.0%) | 94.0% | 100.0% |

### v1 against v2 on the test split (one judgment each)

| Family | Items | v1 pass recall | v1 fail recall | v2 pass recall | v2 fail recall |
|---|---|---|---|---|---|
| review | 469 | 96.0% | 75.6% | 97.0% | 97.4% |
| claim | 142 | 100.0% | 62.9% | 100.0% | 100.0% |
| suggest | 100 | 86.0% | 96.0% | 94.0% | 100.0% |

Judge alone on rule-checkable errors: 145/145 (100.0%; 97.4%–100.0%) caught (review 97/97 (100.0%; 96.2%–100.0%), claim 48/48 (100.0%; 92.6%–100.0%)).

## 3. Regulator and court decisions

| Group | Ads | Agreement | Kappa | Breaches found | Cleared ads cleared |
|---|---|---|---|---|---|
| all | 46 | 39/46 (84.8%; 71.8%–92.4%) | 0.594 (0.284–0.843) | 31/35 (88.6%; 74.0%–95.5%) | 8/11 (72.7%; 43.4%–90.3%) |
| en | 30 | 26/30 (86.7%; 70.3%–94.7%) |  | 20/23 (87.0%; 67.9%–95.5%) | 6/7 (85.7%; 48.7%–97.4%) |
| zh | 16 | 13/16 (81.2%; 57.0%–93.4%) |  | 11/12 (91.7%; 64.6%–98.5%) | 2/4 (50.0%; 15.0%–85.0%) |
| evidence_dependent | 11 | 6/11 (54.5%; 28.0%–78.7%) |  | 4/7 (57.1%; 25.0%–84.2%) | 2/4 (50.0%; 15.0%–85.0%) |
| on_the_face | 35 | 33/35 (94.3%; 81.4%–98.4%) |  | 27/28 (96.4%; 82.3%–99.4%) | 6/7 (85.7%; 48.7%–97.4%) |

AC1: 0.757. Three judgments identical: 45/46 (97.8%; 88.7%–99.6%). First judgment marked unsure: 24/46 (52.2%; 38.1%–65.9%).

## 4. Human ratings that ship with public datasets

### Judge's Verdict (0 / 0.5 / 1, three annotators)

| Measure | Value |
|---|---|
| Judge vs annotators' median, exact | 147/200 (73.5%; 67.0%–79.1%) |
| Judge vs median, weighted kappa | 0.796 (0.725–0.856) |
| Annotator pairs, exact agreement (min–max) | 62.5%–67.5% (mean 64.3%) |
| Judge vs each annotator, exact (mean) | 67.3% |
| Annotator pairs, weighted kappa (min–max) | 0.450–0.606 (mean 0.523) |
| Judge vs each annotator, weighted kappa (mean) | 0.686 |
| Three judgments identical | 181/200 (90.5%; 85.6%–93.8%) |

| Annotators | Items | Exact | Weighted kappa |
|---|---|---|---|
| annotators_agree | 97 | 88/97 (90.7%; 83.3%–95.0%) | 0.949 |
| annotators_split | 103 | 59/103 (57.3%; 47.6%–66.4%) | 0.599 |

### SummEval (1–5, three experts)

| Dimension | Items | Spearman (judge vs experts) | Kendall | Expert ceiling | Crowd vs experts | Mean score judge / experts | Three judgments within 1 |
|---|---|---|---|---|---|---|---|
| coherence | 120 | 0.536 (0.397–0.652) | 0.420 | 0.720 | 0.054 | 2.16 / 3.45 | 120/120 (100.0%; 96.9%–100.0%) |
| consistency | 120 | 0.682 (0.541–0.801) | 0.633 | 0.633 | -0.093 | 4.42 / 4.74 | 119/120 (99.2%; 95.4%–99.9%) |
| fluency | 120 | 0.408 (0.235–0.553) | 0.357 | 0.588 | -0.106 | 2.19 / 4.68 | 120/120 (100.0%; 96.9%–100.0%) |
| relevance | 120 | 0.463 (0.333–0.572) | 0.360 | 0.514 | -0.106 | 3.06 / 3.87 | 120/120 (100.0%; 96.9%–100.0%) |

### WMT MQM, Chinese to English

| Measure | Value |
|---|---|
| Exact (3 classes) | 105/240 (43.8%; 37.6%–50.1%) |
| Weighted kappa | 0.290 (0.170–0.400) |
| Recall: none | 26/80 (32.5%; 23.2%–43.4%) |
| Recall: minor | 50/80 (62.5%; 51.5%–72.3%) |
| Recall: major | 29/80 (36.2%; 26.6%–47.2%) |
| Any error found (minor or major) | 129/160 (80.6%; 73.8%–86.0%) |
| Three judgments identical | 188/240 (78.3%; 72.7%–83.1%) |

| Domain | Items | Exact | Weighted kappa |
|---|---|---|---|
| conversation | 60 | 22/60 (36.7%; 25.6%–49.3%) | 0.242 |
| ecommerce | 60 | 25/60 (41.7%; 30.1%–54.3%) | 0.145 |
| news | 60 | 28/60 (46.7%; 34.6%–59.1%) | 0.274 |
| social | 60 | 30/60 (50.0%; 37.7%–62.3%) | 0.471 |

Confusion (truth, judge; 0 none, 1 minor, 2 major): truth 0 judge 0: 26, truth 0 judge 1: 49, truth 0 judge 2: 5, truth 1 judge 0: 19, truth 1 judge 1: 50, truth 1 judge 2: 11, truth 2 judge 0: 12, truth 2 judge 1: 39, truth 2 judge 2: 29

## 5. Objective errors, subjective ratings: what can be left to whom

| Family | Dimension | Measure | Value | Stable | Group |
|---|---|---|---|---|---|
| review | clause | errors caught | 0.985 | 100.0% | judge-reliable |
| review | correct | pass recall | 0.980 | 95.5% | judge-reliable |
| review | decision | errors caught | 0.963 | 95.3% | judge-reliable |
| review | format | errors caught | 1.000 | 100.0% | rule-checkable |
| review | quote | errors caught | 1.000 | 100.0% | rule-checkable |
| claim | correct | pass recall | 1.000 | 100.0% | judge-reliable |
| claim | figure | errors caught | 1.000 | 100.0% | rule-checkable |
| claim | foreign | errors caught | 1.000 | 100.0% | rule-checkable |
| claim | misreading | errors caught | 1.000 | 100.0% | judge-reliable |
| claim | quote | errors caught | 1.000 | 100.0% | rule-checkable |
| suggest | absence_as_false | errors caught | 1.000 | 100.0% | judge-reliable |
| suggest | contradicts | errors caught | 1.000 | 100.0% | judge-reliable |
| suggest | correct | pass recall | 0.940 | 98.0% | judge-reliable |
| suggest | drops_confirmed | errors caught | 1.000 | 100.0% | judge-reliable |
| suggest | invents | errors caught | 1.000 | 100.0% | judge-reliable |
| suggest | vague | errors caught | 1.000 | 100.0% | judge-reliable |
| regulator | evidence_dependent | agreement | 0.545 | 97.8% | needs people |
| regulator | on_the_face | agreement | 0.943 | 97.8% | judge-reliable |
| jv | annotators_agree | weighted kappa | 0.949 | 90.5% | judge-reliable |
| jv | annotators_split | weighted kappa | 0.599 | 90.5% | needs people |
| summeval | coherence | Spearman | 0.536 | 100.0% | needs people |
| summeval | consistency | Spearman | 0.682 | 99.2% | judge-reliable |
| summeval | fluency | Spearman | 0.408 | 100.0% | needs people |
| summeval | relevance | Spearman | 0.463 | 100.0% | needs people |
| mqm | conversation | weighted kappa | 0.242 | 78.3% | needs people |
| mqm | ecommerce | weighted kappa | 0.145 | 78.3% | needs people |
| mqm | news | weighted kappa | 0.274 | 78.3% | needs people |
| mqm | social | weighted kappa | 0.471 | 78.3% | needs people |

## 6. Rules, judge and a review queue

A judge only; B rules then one judgment, unsure to the queue; C rules then two judgments, unsure or split to the queue.

| Arm | Decided automatically | Errors missed | False alarms | Queue | Judge calls | USD per 1,000 items |
|---|---|---|---|---|---|---|
| A | 711/711 (100.0%; 99.5%–100.0%) | 7/390 (1.8%; 0.9%–3.7%) | 9/321 (2.8%; 1.5%–5.2%) | 0/711 (0.0%; 0.0%–0.5%) | 711 | 0.303 |
| B | 662/711 (93.1%; 91.0%–94.7%) | 2/390 (0.5%; 0.1%–1.9%) | 3/321 (0.9%; 0.3%–2.7%) | 49/711 (6.9%; 5.3%–9.0%) | 566 | 0.243 |
| C | 644/711 (90.6%; 88.2%–92.5%) | 2/390 (0.5%; 0.1%–1.9%) | 2/321 (0.6%; 0.2%–2.2%) | 67/711 (9.4%; 7.5%–11.8%) | 1132 | 0.487 |

| Family | Missed, A | Missed, B | Queue, B |
|---|---|---|---|
| review | 7/270 (2.6%; 1.3%–5.3%) | 2/270 (0.7%; 0.2%–2.7%) | 46/469 (9.8%; 7.4%–12.8%) |
| claim | 0/70 (0.0%; 0.0%–5.2%) | 0/70 (0.0%; 0.0%–5.2%) | 0/142 (0.0%; 0.0%–2.6%) |
| suggest | 0/50 (0.0%; 0.0%–7.1%) | 0/50 (0.0%; 0.0%–7.1%) | 3/100 (3.0%; 1.0%–8.5%) |

Error rate of first judgments marked sure: 5/662 (0.8%; 0.3%–1.8%); marked unsure: 11/49 (22.4%; 13.0%–35.9%).

## 7. Sensitivity

r1 reworded rubric in another order; r2 terse rubric; swap answer options in the other order; verbose a long content-free passage added to the candidate; assertive one sentence of assurance added; low effort low.

| Change | Items | Verdicts changed | Accuracy before → after | McNemar p | Wrong ones passed before → after | USD per 1,000 calls |
|---|---|---|---|---|---|---|
| repeat (noise floor) | 368 | 3/368 (0.8%; 0.3%–2.4%) |  |  |  |  |
| r1 | 368 | 2/368 (0.5%; 0.1%–2.0%) | 98.4% → 97.8% | 0.500 | 0.5% → 1.0% | 0.220 |
| r2 | 368 | 7/368 (1.9%; 0.9%–3.9%) | 98.4% → 96.5% | 0.016 | 0.5% → 1.0% | 0.201 |
| swap | 368 | 2/368 (0.5%; 0.1%–2.0%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.0% | 0.219 |
| verbose | 368 | 0/368 (0.0%; 0.0%–1.0%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.5% | 0.216 |
| assertive | 368 | 0/368 (0.0%; 0.0%–1.0%) | 98.4% → 98.4% | 1.000 | 0.5% → 0.5% | 0.215 |
| low | 368 | 5/368 (1.4%; 0.6%–3.1%) | 98.4% → 98.6% | 1.000 | 0.5% → 0.0% | 0.182 |

Base cost per call on this subsample: 0.212 USD per 1,000 calls.

| Change | review | claim | suggest |
|---|---|---|---|
| r1 | 2/126 (1.6%; 0.4%–5.6%) | 0/142 (0.0%; 0.0%–2.6%) | 0/100 (0.0%; 0.0%–3.7%) |
| r2 | 0/126 (0.0%; 0.0%–3.0%) | 0/142 (0.0%; 0.0%–2.6%) | 7/100 (7.0%; 3.4%–13.7%) |
| swap | 2/126 (1.6%; 0.4%–5.6%) | 0/142 (0.0%; 0.0%–2.6%) | 0/100 (0.0%; 0.0%–3.7%) |
| verbose | 0/126 (0.0%; 0.0%–3.0%) | 0/142 (0.0%; 0.0%–2.6%) | 0/100 (0.0%; 0.0%–3.7%) |
| assertive | 0/126 (0.0%; 0.0%–3.0%) | 0/142 (0.0%; 0.0%–2.6%) | 0/100 (0.0%; 0.0%–3.7%) |
| low | 3/126 (2.4%; 0.8%–6.8%) | 0/142 (0.0%; 0.0%–2.6%) | 2/100 (2.0%; 0.6%–7.0%) |

## 8. Position and order

| Pairs | Pairs | Right when shown first | Right when shown second | Same pick both orders |
|---|---|---|---|---|
| all | 157 | 152/157 (96.8%; 92.8%–98.6%) | 153/157 (97.5%; 93.6%–99.0%) | 154/157 (98.1%; 94.5%–99.3%) |
| review | 107 | 102/107 (95.3%; 89.5%–98.0%) | 103/107 (96.3%; 90.8%–98.5%) | 104/107 (97.2%; 92.1%–99.0%) |
| suggest | 50 | 50/50 (100.0%; 92.9%–100.0%) | 50/50 (100.0%; 92.9%–100.0%) | 50/50 (100.0%; 92.9%–100.0%) |

Inconsistent pairs: picked A both times 1, picked B both times 2. McNemar (first vs second) p = 1.000. Both items judged right one at a time: 144/157 (91.7%; 86.3%–95.1%).

Lists (16 resumes, 142 verdicts): same verdict in both orders 139/142 (97.9%; 94.0%–99.3%); accuracy in lists 140/142 (98.6%; 95.0%–99.6%) against one at a time 142/142 (100.0%; 97.4%–100.0%).

## 9. Quality-check agent

239 test records (119 with one planted error, 120 correct).

| Check | Wrong records caught | Correct records flagged | decision | category | span_semantic | span_altered | unknown_clause |
|---|---|---|---|---|---|---|---|
| script | 18/119 (15.1%; 9.8%–22.6%) | 0/120 (0.0%; 0.0%–3.1%) | 0/65 (0.0%; 0.0%–5.6%) | 0/22 (0.0%; 0.0%–14.9%) | 0/14 (0.0%; 0.0%–21.5%) | 10/10 (100.0%; 72.2%–100.0%) | 8/8 (100.0%; 67.6%–100.0%) |
| agent | 119/119 (100.0%; 96.9%–100.0%) | 6/120 (5.0%; 2.3%–10.5%) | 65/65 (100.0%; 94.4%–100.0%) | 22/22 (100.0%; 85.1%–100.0%) | 14/14 (100.0%; 78.5%–100.0%) | 10/10 (100.0%; 72.2%–100.0%) | 8/8 (100.0%; 67.6%–100.0%) |
| pipeline | 119/119 (100.0%; 96.9%–100.0%) | 6/120 (5.0%; 2.3%–10.5%) | 65/65 (100.0%; 94.4%–100.0%) | 22/22 (100.0%; 85.1%–100.0%) | 14/14 (100.0%; 78.5%–100.0%) | 10/10 (100.0%; 72.2%–100.0%) | 8/8 (100.0%; 67.6%–100.0%) |

Agent: 2.88 tool calls per record (0 records with none); problem named right on 114/119 (95.8%; 90.5%–98.2%) of the wrong records it caught; 0.520 USD per 1,000 records alone, 0.480 after the script.

### Acceptance standard, simulated batches of 100 records

| True error rate | Accepted | Failed S1 | Failed S2 | Failed S3 |
|---|---|---|---|---|
| 0% | 99.1% | 0.0% | 0.9% | 0.0% |
| 1% | 96.2% | 0.1% | 3.6% | 0.0% |
| 2% | 91.5% | 0.2% | 8.2% | 0.0% |
| 5% | 62.0% | 4.1% | 35.8% | 0.0% |
| 10% | 13.6% | 19.5% | 83.5% | 0.0% |
| 20% | 0.1% | 59.8% | 99.9% | 0.0% |

Targets: accept_at_<=2%: met, reject_at_>=10%: not met

## 10. A second judge (claude-sonnet-5-5, one judgment)

| Family | Items | claude-haiku-5-5 right | claude-sonnet-5-5 right | Same verdict | McNemar p |
|---|---|---|---|---|---|
| claim | 40 | 40/40 (100.0%; 91.2%–100.0%) | 40/40 (100.0%; 91.2%–100.0%) | 40/40 (100.0%; 91.2%–100.0%) | 1.000 |
| mqm | 40 | 18/40 (45.0%; 30.7%–60.2%) | 21/40 (52.5%; 37.5%–67.1%) | 29/40 (72.5%; 57.2%–83.9%) | 0.508 |
| suggest | 40 | 40/40 (100.0%; 91.2%–100.0%) | 39/40 (97.5%; 87.1%–99.6%) | 39/40 (97.5%; 87.1%–99.6%) | 1.000 |

claude-sonnet-5-5 cost 1.483 USD per 1,000 calls (batch price).

## Predictions

| # | Prediction | Result |
|---|---|---|
| 1 | judge alone catches < 95% of rule-checkable errors | not held |
| 2 | regulator agreement lower than constructed agreement | held |
| 3 | lower on evidence-dependent decisions | held |
| 4 | jv: judge mean pairwise exact agreement within the human range | held |
| 5 | summeval: judge below the expert ceiling on all four dimensions | not held |
| 6 | three judgments identical less often on human-rated families | held |
| 7 | assurance raises the pass rate of wrong candidates by >= 2 points | not held |
| 8 | rewording flips more verdicts than repeating | not held |
| 9 | pairs: same pick in both orders >= 90% | held |
| 10 | B misses fewer errors than A with a queue <= 20% | held |
| 11 | script then agent catches >= 90% and flags <= 10% of correct records | held |
| 12 | acceptance standard meets both targets | not held |

## Cost (batch price where batched)

| Stage | Calls | Input tokens | Output tokens | USD |
|---|---|---|---|---|
| dev | 780 | 2798390 | 296463 | 0.2140 |
| flips | 288 | 1630012 | 292580 | 0.1546 |
| list | 32 | 87062 | 45004 | 0.0156 |
| main | 5742 | 14810153 | 1540722 | 1.1257 |
| pair | 314 | 1387678 | 97905 | 0.0939 |
| perturb | 2208 | 5992988 | 646644 | 0.4613 |
| pilot | 40 | 90795 | 12374 | 0.0153 |
| qc-pilot | 13 | 33052 | 3240 | 0.0049 |
| qc | 491 | 1583644 | 165920 | 0.1242 |
| second-estimate | 5 | 5261 | 456 | 0.0151 |
| second | 120 | 112764 | 13041 | 0.1780 |

Total: 2.4026 USD.

## Details used in the text

- Constructed-answer disagreements: 12; tracing to the answer key: 5; left to the judge: 7.
- Argued wrong-decision reviews passed: 4, of them first judgment unsure: 3; swapped clauses passed: 1; right reviews of trap ads failed: 2.
- Regulator misses: 7, of them evidence-dependent: 5.
- Judge's Verdict items with median 0.5: 22; judge gave 0.5 to: 9.
- Terse rubric: good suggestions failed 6, of them with an empty rewrite field 6; bad suggestions passed 1.
- Queue: C queued 18 more items than B; review items in B's queue: 46.
- Rule checks on the source projects' stored answers: 1 of 376 right reviews flagged; 3 of 103 right resume verdicts flagged.
- Judge price per 1,000 judgments (batch): review 0.400 USD, claim 0.121 USD, suggest 0.109 USD.
- Total calls: 10,033; spent before the second judge: 2.21 USD; second judge with its estimate: 125 calls, 0.1931 USD.
- QC agent false flags by problem named: category_or_clause 3, format 3; records settled by the script: 18.
- Second judge on its 120 items: 1.483 USD per 1,000 calls against 0.114 for claude-haiku-5-5 on the same items, 13 times as much; clean translations called flawed: 8 of 9.
