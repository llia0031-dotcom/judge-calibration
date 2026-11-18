# Where the items come from

| File | Source | Licence | What is included |
|---|---|---|---|
| `review.jsonl`, `qc.jsonl` | [Grounded Review](https://github.com/llia0031-dotcom/grounded-review) test ads, answer keys and stored reviews | MIT | everything; English policy quotes are replaced by the clause id and a link to the TikTok policy page, whose text is not redistributed |
| `claim.jsonl` | [Evidence Screening](https://github.com/llia0031-dotcom/evidence-screening) synthetic resumes, postings and verdicts | MIT | everything |
| `suggest.jsonl` | [Sellpoint Check](https://github.com/llia0031-dotcom/sellpoint-check) constructed test sets and suggestion calibration pairs | MIT | everything |
| `jv.jsonl` | [nvidia/judges-verdict](https://huggingface.co/datasets/nvidia/judges-verdict), file `annotations_train.json` | CC BY-SA 4.0 | all 200 items with their three annotations, reformatted; this file is licensed CC BY-SA 4.0 |
| `mqm.jsonl` | [google/wmt-mqm-human-evaluation](https://github.com/google/wmt-mqm-human-evaluation) via [RicardoRei/wmt-mqm-human-evaluation](https://huggingface.co/datasets/RicardoRei/wmt-mqm-human-evaluation) | Apache-2.0 | 240 Chinese-to-English segments of 2022 with their MQM scores |
| `summeval.jsonl` | [SummEval](https://github.com/Yale-LILY/SummEval) expert and crowd annotations | MIT | ids, summaries and scores; the CNN/DailyMail articles are not redistributed |
| `regulator.jsonl` | 30 UK ASA rulings and 16 Chinese regulator and court cases | — | ids, decisions, dates and links; the ad descriptions are not redistributed |
| `../images/` | rendered by Grounded Review's image renderer (fictional brands) | MIT | the ad images |
