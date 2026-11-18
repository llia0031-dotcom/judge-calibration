# 模型裁判校准（Judge Calibration）

模型裁判能信到什么程度？这个项目拿一个裁判（claude-haiku-5-5 按写好的评分表判对错、打分），分别和三种参照比：出题时就定好的答案、监管机构和法院公布的结论、公开数据集自带的人工评分，三种分开算。然后定出哪些检查交给脚本、哪些可以交给裁判、哪些要留给人，再用一个质检 Agent 检查标注记录，配一份能量化的验收标准。所有做法在第一次判题之前就写进了预注册。

[English](README.md)

## 在整套项目里的位置

这个项目属于同一套项目，主线是“让 AI 拿出证据”。其中好几个项目都用“模型按评分表判”来打分，这个项目专门量这个打分的裁判本身。

- **[有据审核 Grounded Review](https://github.com/llia0031-dotcom/grounded-review)**：按广告规则审广告，引出违规的原话。它的测试广告、答案和存下的审核意见是这里最大的一组题（含图片广告）；它的 46 个监管和法院案例是“监管裁决”这一种参照。
- **[有据可查的简历初筛 Evidence Screening](https://github.com/llia0031-dotcom/evidence-screening)**：对照岗位要求查简历并引原文。它的“符合要求”判断和 40 条植入的看错意思，是这里的 claim 组。
- **[卖点体检 Sellpoint Check](https://github.com/llia0031-dotcom/sellpoint-check)**：用评分表给“卖点修改建议”打分，打分前先用好坏成对的建议校准过评分方。那些成对的建议是这里的 suggest 组。
- **[有据可查 evidence-check](https://github.com/llia0031-dotcom/evidence-check)**：这里的规则层。“引文是不是原话、数字在不在引文里”都用它的核对脚本查；报告里的每个数字也用它对回 `eval/results/summary.json`。
- **[有据标注流水线 Grounded Labelling Pipeline](https://github.com/llia0031-dotcom/grounded-labelling-pipeline)**：把拿不准的判断送进复核队列，由人来定。报告第 6 节量的是：裁判加进来以后，这样一个队列能换来多少。
- **[Evidence First](https://github.com/llia0031-dotcom/evidence-first)**：汇总所有项目的评测卡。

## 结论

| 问题 | 结果 |
|---|---|
| 裁判和出题时定好的答案一致吗？ | 在这些题上一致：广告审核意见、简历判断、卖点修改建议共 711 道，699 道一致（98.3%，Cohen's kappa 0.966）；植入的 390 处错误抓到 385 处；711 道里 696 道三次判得一样。12 处不一致里有 5 处是答案本身的问题，不是裁判的问题。 |
| 和监管机构、法院的结论一致吗？ | 差一些：46 个公开结论里一致 39 个（84.8%）。能从广告本身看出结论的 35 个里对 33 个；结论取决于广告以外证据的 11 个里只对 6 个。 |
| 和公开数据集自带的人工评分一致吗？ | 粗粒度的打分接近：Judge's Verdict 上，裁判和每位标注员的一致率是 67.3%，落在标注员彼此之间的 62.5% 到 67.5% 之内。摘要质量中等：SummEval 的 Spearman 从 0.408（流畅度）到 0.682（事实一致）。翻译错误的轻重判断弱：WMT MQM 加权 kappa 0.290。 |
| 哪些交给脚本，哪些交给裁判？ | 脚本：引文不是原话、数字不在引文里、条款编号不存在、记录格式不对。这 145 处裁判也全抓到了，但脚本不花钱、也不会错。裁判：有事实可依的客观错误（结论判反、条款引错、看错简历、编造商品属性），每一类都抓到 96.3% 以上。人：标注员之间本来就有分歧的评分，以及要靠外部证据才能定的结论。 |
| 规则、裁判、复核队列一起用效果如何？ | 先跑规则，再判一次，裁判自己标“拿不准”的进复核队列：390 处错误漏掉 2 处，6.9% 的题进队列；只用裁判漏掉 7 处。前一种还更便宜（每 1,000 道 0.243 美元对 0.303 美元），因为规则先拦下的不用再调模型。裁判的“拿不准”很有用：它说“确定”的判断错 0.8%，说“拿不准”的错 22.4%。 |
| 换说法、换顺序、加废话会让它判偏吗？ | 在这些题上几乎不会。给候选答案加一大段“我做得很仔细”或一句“我已逐项核对”，368 道里一道都没变；把选项顺序反过来，变了 2 道；评分表改成简短版，100 条修改建议里变了 7 条。成对比较时，157 对里有 154 对两种顺序选的是同一个。 |
| 能用 Agent 质检标注记录吗？ | 给它两个工具（这段原话在广告里吗？这条条款原文是什么？），239 条记录里植入的 119 处错误全部查出，120 条正确记录误报 6 条，每 1,000 条 0.52 美元。基于它定的验收标准：错误率 2% 的批次 91.5% 能通过，但错误率 10% 的批次也有 13.6% 能通过，第二个目标没达到。 |
| 换更大的模型当裁判有用吗？ | 这里没用。claude-sonnet-5-5 在同样 120 道题上贵 13 倍，简历判断和修改建议上和 claude-haiku-5-5 一样，翻译轻重 40 道里多对 3 道（p = 0.508）。 |

预注册的 12 条预测里 7 条成立、5 条不成立，每条和结果都列在 [`eval/EVALUATION.md`](eval/EVALUATION.md)（英文）。上面每个数字都用 evidence-check 对回了 [`eval/results/RESULTS.md`](eval/results/RESULTS.md)（`tools/check_numbers.py`，核对记录在 `eval/results/claims.json`）。整个项目调用接口共花 2.40 美元。

## 怎么跑

Python 3.12。

```bash
pip install -r requirements.txt
python run_all.py --offline    # 用存下的答案重新打分并跑测试，不调用模型
```

`python run_all.py` 会把还没跑完的阶段用批量接口跑完，已经有答案的请求不会再发。接口密钥从 `EVAL_ENV_FILE` 指的文件里读（一行 `ANTHROPIC_API_KEY=...`，见 `.env.example`）。

这个仓库里重建不了的部分：

- 监管案例的广告描述和 SummEval 的新闻原文不转载，`data/items/regulator.jsonl` 和 `data/items/summeval.jsonl` 只有编号、答案和链接；在这些题上存下的判断都在仓库里，可以离线重新打分；
- TikTok 广告政策原文不转载。`data/policy/tiktok.stub.json` 只有条款编号、标题和链接，题目里英文条款的引文换成了条款编号加链接。要重新判英文审核题，需要从这些链接取原文。

## 目录

| 文件夹 | 内容 |
|---|---|
| `judgecal/` | 裁判提示词（v1–v4，评分表三种措辞）、规则检查、批量调用、统计 |
| `eval/` | 建题、分阶段运行、质检 Agent、打分、预注册、报告 |
| `eval/results/` | `summary.json`（所有数字）、`RESULTS.md`（所有表格）、`raw/`（存下的每一次判断） |
| `data/items/` | 七组题和质检记录，附来源和许可证 |
| `data/images/` | 图片广告（脚本画的，品牌是虚构的） |
| `data/policy/` | 中国法规条款库；TikTok 条款索引 |
| `tests/` | 离线测试 |

## 用到的公开数据和工具

| 名称 | 用来做什么 | 许可证 |
|---|---|---|
| [nvidia/judges-verdict](https://huggingface.co/datasets/nvidia/judges-verdict) | 带人工评分的 RAG 回答（每条三位标注员） | CC BY-SA 4.0；`data/items/jv.jsonl` 沿用 |
| [SummEval](https://github.com/Yale-LILY/SummEval) | 专家打分的新闻摘要 | MIT（评分）；不含新闻原文 |
| [WMT MQM 人工评测](https://github.com/google/wmt-mqm-human-evaluation) | 专业译员按 MQM 标过错的中译英 | Apache-2.0 |
| [scikit-learn](https://scikit-learn.org)、[statsmodels](https://www.statsmodels.org)、[SciPy](https://scipy.org) | kappa、Wilson 区间、Fleiss kappa、相关系数、精确检验 | BSD-3-Clause |

做法照已发表的工作：按写明的标准打分（G-Eval），成对比较交换顺序、位置偏差、长答案偏好和偏向自家答案（MT-Bench），先校验裁判再用、评分标准会漂移（EvalGen），带工具的裁判（Agent-as-a-Judge），偏差注入（CALM），拿不准的交给人（Trust or Escalate）。没有复制代码。

## 局限

- **只有一个裁判、跑一次。** 换模型、换日期、换设置结果可能不同；另一个模型只比了 120 道题。
- **构造的答案只和定答案的规则一样好。** 有 5 处是答案本身比裁判弱。植入的错误只有几种，真实的审核意见会以更多方式出错。
- **“论证成错误结论”的审核意见和裁判是同一个模型写的**，这可能让裁判更容易或更难识破。
- **有些组很小。** 监管结论 46 个，其中依赖外部证据的 11 个；有些错误类型只有 4 到 22 道。表里都给了 95% 区间。
- **简历判断已经到顶。** 裁判全对，这一组分不出提示词或模型的高低了。
- **复核队列按“全部改对”计算**，这是复核员能做到的最好情况，不是实测。
- **没有为这个项目做任何人工评分。** 人工参照都是数据集自带的。

## 许可证

MIT。`data/items/jv.jsonl` 是 CC BY-SA 4.0，其余数据文件见 `data/items/LICENSES.md`。
