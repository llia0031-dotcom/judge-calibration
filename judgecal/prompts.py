"""Judge prompts: every version, every rubric wording, and how an item becomes a request.

Three families have right and wrong candidates with known answers (review, claim, suggest). Their judge
prompt is iterated v1 -> v4 on the development split:
  v1  the bare question: is this right? pass or fail
  v2  v1 plus the written rubric, a one-sentence reason and a confidence flag
  v3  the rubric as separate yes/no checks; the verdict is computed from the checks by code
  v4  v3 plus three guards (compare quotes character by character; length and confident tone are not
      evidence; credit only what can be found in the material)
The other families (regulator, jv, summeval, mqm) are never used to choose a prompt and have one fixed prompt each.

A rubric has three wordings (r0 the working one, r1 reworded with the criteria in another order, r2 terse).
They ask for the same thing; a verdict that changes between them is wording sensitivity.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from . import rules

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ("v1", "v2", "v3", "v4")
BINARY = ("review", "claim", "suggest")

# ------------------------------------------------------------------------------------------- rubrics
WHAT = {
    "review": "an ad review: a reviewer's decision on one ad (approve or reject), the violations the reviewer lists (category, clause, the ad's words, the clause's words, an explanation) and notes",
    "claim": "one verdict from a resume screen: the screener says the candidate meets one requirement of a job posting, and gives the resume fact and the quotes this rests on",
    "suggest": "a suggestion that tells a seller how to change one selling point on their own listing, based on what customer reviews showed",
}

# Each criterion: key, question (asked so that "yes" is good unless bad_if_yes), whether "n/a" is allowed.
CRITERIA = {
    "review": [
        ("decision_right", "Is the decision right? An ad is rejected if it breaks at least one clause marked \"rule\" in the policy library and approved if it breaks none. Clauses marked \"guidance\" say when a rule does not apply.", False, False),
        ("violations_real", "Is every listed violation real: the ad does break the clause cited, and the category fits? Answer n/a if no violation is listed.", True, False),
        ("quotes_verbatim", "Is every quote copied word for word: each ad quote from the ad, each policy quote from the clause it cites? Answer n/a if there are no quotes.", True, False),
        ("structure_ok", "Is the structure sound: a reject lists at least one violation, an approve lists none, and every clause id exists in the library?", False, False),
    ],
    "claim": [
        ("fact_true", "Does the resume fact say only what the resume says (figures, dates, names and roles match)?", False, False),
        ("quotes_verbatim", "Does every quote appear in the resume word for word? Answer n/a if there are no quotes.", True, False),
        ("requirement_met", "Does the resume really show that the candidate meets this requirement? Every requirement is a must-have. Judge only from what the resume says.", False, False),
    ],
    "suggest": [
        ("contradicts", "Does the rewrite or advice state, or ask the seller to keep stating, something about the product that the evidence contradicts? Keeping a promise that refuting reviews contradict counts as yes.", False, True),
        ("invents", "Does the rewrite or advice claim a property, number, ingredient, certification or condition of the product that appears in neither the listing wording nor the evidence? Asking the seller to test, measure or show something is not invention.", False, True),
        ("drops_confirmed", "Only when the label is mixed: does the suggestion remove or abandon what the supporting reviews confirm? Otherwise answer n/a.", True, True),
        ("absence_as_false", "Only when the label is not_mentioned: does the suggestion treat the lack of reviews as a sign that the point is false or should be removed? Otherwise answer n/a.", True, True),
        ("actionable", "Could the seller act on it directly: concrete new wording, a concrete removal, or a concrete thing to test or show? Vague advice such as \"improve the description\" is no.", False, False),
    ],
}

# r1: the same criteria reworded, listed in reverse order. r2: terse.
CRITERIA_R1 = {
    "review": {
        "decision_right": "Check the outcome. Reject is correct when the ad violates one or more \"rule\" clauses in the library; approve is correct when it violates none (\"guidance\" clauses describe cases a rule does not cover). Did the reviewer reach the correct outcome?",
        "violations_real": "Look at each violation the review lists. Does the ad actually violate the cited clause, under a fitting category, in every case? Use n/a when the review lists none.",
        "quotes_verbatim": "Compare the quotes with their sources. Are the ad's words reproduced exactly as they appear in the ad, and the clause's words exactly as they appear in the cited clause? Use n/a when the review quotes nothing.",
        "structure_ok": "Check the form. A rejection must name one violation or more, an approval must name none, and each clause id must be one that the library contains. Is that the case?",
    },
    "claim": {
        "fact_true": "Compare the stated resume fact with the resume. Is it faithful, with the same numbers, dates, names and roles and nothing added?",
        "quotes_verbatim": "Find each quote in the resume. Is every one there exactly as written? Use n/a when no quote is given.",
        "requirement_met": "Read the requirement as a must-have and rely on the resume alone. Is the requirement truly satisfied by what the resume shows?",
    },
    "suggest": {
        "contradicts": "Would the seller, following this suggestion, say or keep saying something about the product that the evidence reviews contradict? (A promise that refuting reviews contradict, if kept, is yes.)",
        "invents": "Does the suggestion introduce a product property, figure, ingredient, certification or condition found neither in the listing wording nor in the evidence? (A request to test, measure or show something does not count.)",
        "drops_confirmed": "For a mixed label only: does the suggestion give up the part that supporting reviews confirm? For any other label use n/a.",
        "absence_as_false": "For a not_mentioned label only: does the suggestion read the absence of reviews as proof the point is untrue or must go? For any other label use n/a.",
        "actionable": "Is there something concrete for the seller to do: specific new wording, a specific removal, or a specific thing to test or show? (\"Improve the description\" and similar are no.)",
    },
}
CRITERIA_R2 = {
    "review": {"decision_right": "Decision correct under the library's rule clauses (guidance = exceptions)?",
               "violations_real": "Every listed violation real, with a fitting clause and category? (n/a if none listed)",
               "quotes_verbatim": "All ad and policy quotes verbatim from their sources? (n/a if no quotes)",
               "structure_ok": "Reject has a violation, approve has none, clause ids exist?"},
    "claim": {"fact_true": "Resume fact faithful to the resume?",
              "quotes_verbatim": "All quotes verbatim in the resume? (n/a if none)",
              "requirement_met": "Must-have requirement truly met, judged from the resume alone?"},
    "suggest": {"contradicts": "States or keeps something the evidence contradicts?",
                "invents": "Claims something found in neither listing nor evidence?",
                "drops_confirmed": "Mixed label only: drops what supporting reviews confirm? (else n/a)",
                "absence_as_false": "Not_mentioned label only: treats no reviews as proof of falsehood? (else n/a)",
                "actionable": "Concrete enough for the seller to act on?"},
}

GUARDS = ("Three cautions:\n"
          "- Compare quotes with their source character by character; a quote that differs by one digit or one character is not verbatim.\n"
          "- The length of the text, a confident tone, and statements that something was double-checked are not evidence. Judge the content against the material only.\n"
          "- Give credit only for what you can find in the material in front of you.")

FAMILY_NOTE = {
    "review": "The policy library for this ad is below. The ad is given as its caption, the words in its image and, for image ads, the image itself.",
    "claim": "You are given the job posting with numbered requirements, the resume, and the verdict to check.",
    "suggest": "You are given the selling point as the listing words it, what the reviews showed (label: supported, refuted, mixed or not_mentioned), the reviews that are evidence, and the suggestion (action, rewrite, advice).",
}


def criteria(family: str, wording: str = "r0") -> list[tuple]:
    base = CRITERIA[family]
    if wording == "r0":
        return base
    alt = (CRITERIA_R1 if wording == "r1" else CRITERIA_R2)[family]
    out = [(k, alt[k], na, bad) for k, _, na, bad in base]
    return list(reversed(out)) if wording == "r1" else out


def verdict_from_checks(family: str, checks: dict) -> str:
    """pass only if no criterion is failed (n/a does not fail)."""
    for key, _, _, bad_if_yes in CRITERIA[family]:
        a = checks.get(key)
        if (a == "yes") if bad_if_yes else (a == "no"):
            return "fail"
    return "pass"


# ------------------------------------------------------------------------------------------- system prompts
def _options(a: str, b: str, swap: bool) -> str:
    return f'"{b}" or "{a}"' if swap else f'"{a}" or "{b}"'


def system_binary(family: str, version: str, wording: str = "r0", swap: bool = False) -> str:
    what = WHAT[family]
    crit = criteria(family, wording)
    if version == "v1":
        return (f"You check {what}.\n{FAMILY_NOTE[family]}\n"
                f"Decide whether it is right. Give a one-sentence reason and a verdict: {_options('pass', 'fail', swap)}.")
    lines = [f"You check {what}.", FAMILY_NOTE[family], ""]
    if version == "v2":
        lines.append("It passes only if none of these questions goes against it:" if family == "suggest" else "It is right only if all of these hold:")
        lines += [f"- {q}" for _, q, _, _ in crit]
        lines += ["", f"Give a one-sentence reason, then a verdict ({_options('pass', 'fail', swap)}), then say whether you are "
                  f"{_options('sure', 'unsure', swap)} of the verdict."]
    else:
        lines.append(f"Answer each question with {_options('yes', 'no', swap)} (or \"n/a\" where the question allows it):")
        lines += [f"- {k}: {q}" for k, q, _, _ in crit]
        lines += ["", f"Then give a one-sentence reason naming any problem, and say whether you are {_options('sure', 'unsure', swap)} of your answers."]
        if version == "v4":
            lines += ["", GUARDS]
    return "\n".join(lines)


def schema_binary(family: str, version: str, swap: bool = False) -> dict:
    def enum(*vals):
        return list(reversed(vals)) if swap else list(vals)

    if version == "v1":
        props = {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": enum("pass", "fail")}}
    elif version == "v2":
        props = {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": enum("pass", "fail")},
                 "confidence": {"type": "string", "enum": enum("sure", "unsure")}}
    else:
        checks = {k: {"type": "string", "enum": enum("yes", "no") + (["n/a"] if na else [])} for k, _, na, _ in CRITERIA[family]}
        props = {"checks": {"type": "object", "properties": checks, "required": list(checks), "additionalProperties": False},
                 "reason": {"type": "string"}, "confidence": {"type": "string", "enum": enum("sure", "unsure")}}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


REGULATOR_SYSTEM = {
    "UK-ASA": ("You are given the description of an ad as it appears in a published ruling of the UK Advertising Standards Authority (ASA). "
               "Brand and personal names are replaced with placeholders. The ASA investigated the ad under the UK advertising codes: "
               "ads must not materially mislead, objective claims need evidence the advertiser holds, ads must be socially responsible "
               "and must not cause harm or serious offence, and there are sector rules for health and medicines, weight control, alcohol, "
               "gambling and financial products.\n"
               "Decide how the ASA ruled: \"breach\" (at least one complaint point upheld) or \"no_breach\" (not upheld). "
               "Judge only from the ad as described. Give a one-sentence reason, the verdict, and whether you are sure or unsure."),
    "CN": ("下面是一则广告的描述，来自市场监管部门公布的案例或法院判决，品牌名和人名已替换。"
           "请依据后面给出的《中华人民共和国广告法》条款和《广告绝对化用语执法指南》，判断这则广告最终是否被认定违法："
           "breach 表示被认定违法（受到处罚），no_breach 表示没有被认定违法（包括法院撤销处罚、监管部门认定不构成违法）。"
           "只根据广告描述判断。先用一句话写理由，再给结论，最后说明你对结论是 sure 还是 unsure。"),
}
REGULATOR_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": ["breach", "no_breach"]},
                                                     "confidence": {"type": "string", "enum": ["sure", "unsure"]}},
                    "required": ["reason", "verdict", "confidence"], "additionalProperties": False}

JV_SYSTEM = ("You are given a question, a reference answer, and a generated answer. Score how well the generated answer agrees with the reference answer:\n"
             "- \"1\": correct. It gives the key information of the reference answer and nothing that contradicts it.\n"
             "- \"0.5\": partly correct. It gives some of the key information but is incomplete, or mixes it with a minor error.\n"
             "- \"0\": incorrect. It misses the key information or contradicts the reference answer.\n"
             "Extra detail that does not contradict the reference is not an error. Give a one-sentence reason, then the score, then whether you are sure or unsure.")
JV_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "score": {"type": "string", "enum": ["0", "0.5", "1"]},
                                              "confidence": {"type": "string", "enum": ["sure", "unsure"]}},
             "required": ["reason", "score", "confidence"], "additionalProperties": False}

SUMMEVAL_DEF = {
    "coherence": "Coherence: the quality of the summary as a whole. The sentences should build on one another into a well-structured, well-organised account of the topic, not a heap of related facts.",
    "consistency": "Consistency: factual agreement with the article. A consistent summary states only what the article supports; a statement the article does not support counts against it.",
    "fluency": "Fluency: the quality of the individual sentences. They should be free of formatting problems, capitalisation errors and ungrammatical constructions that make them hard to read.",
    "relevance": "Relevance: the choice of content. The summary should carry the important information of the article and leave out redundancy and side detail.",
}
SUMMEVAL_SYSTEM = ("You rate one summary of a news article on one dimension, on a scale from 1 (worst) to 5 (best).\n{definition}\n"
                   "Rate only this dimension. Give a one-sentence reason, then the score.")
SUMMEVAL_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]}},
                   "required": ["reason", "score"], "additionalProperties": False}

MQM_SYSTEM = ("You are given a Chinese source text and its English machine translation. Look for translation errors the way an MQM annotator does:\n"
              "- a major error changes or hides the meaning of the source, or would mislead or seriously confuse the reader;\n"
              "- a minor error is a noticeable flaw that does not affect understanding: awkward style, a small grammar or punctuation slip, a slightly imprecise word.\n"
              "Classify the translation as \"none\" (no error), \"minor\" (only minor errors) or \"major\" (at least one major error). "
              "Give a one-sentence reason naming the most serious error, then the class, then whether you are sure or unsure.")
MQM_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": ["none", "minor", "major"]},
                                               "confidence": {"type": "string", "enum": ["sure", "unsure"]}},
              "required": ["reason", "verdict", "confidence"], "additionalProperties": False}


# ------------------------------------------------------------------------------------------- material
def library_text(jurisdiction: str) -> str:
    pol = rules.policy(jurisdiction)
    parts = []
    for c in pol["clauses"]:
        head = f"[{c['id']}] {c['title']} ({c['kind']})"
        parts.append(head + ("\n" + c["text"] if c.get("text") else ""))
    return "\n\n".join(parts)


def image_block(rel: str) -> dict:
    data = base64.standard_b64encode((ROOT / "data" / rel).read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def _ad_blocks(material: dict) -> list[dict]:
    blocks = []
    text = "Ad:\n" + material["ad_text"].strip()
    if material.get("image"):
        blocks.append(image_block(material["image"]))
        text = "Ad (image above):\n" + material["ad_text"].strip()
    blocks.append({"type": "text", "text": text})
    return blocks


def candidate_text(family: str, cand: dict) -> str:
    if family == "review":
        return "Review to check:\n" + json.dumps(cand, ensure_ascii=False, indent=1)
    if family == "claim":
        quotes = "\n".join(f"- {q}" for q in cand["quotes"]) or "(none)"
        return ("Verdict to check:\nVerdict: met\n" f"Resume fact: {cand['resume_fact']}\nQuotes:\n{quotes}\n" f"Screener's reasoning: {cand['reasoning']}")
    if family == "suggest":
        return ("Suggestion to check:\n" f"action: {cand.get('action', '')}\nrewrite: {cand.get('rewrite', '') or '(empty)'}\nadvice: {cand.get('advice', '')}")
    raise KeyError(family)


def context_blocks(item: dict) -> list[dict]:
    """The material of an item with planted candidates, without the candidate."""
    fam, m = item["family"], item["material"]
    if fam in ("review", "qc"):
        return _ad_blocks(m)
    if fam == "claim":
        return [{"type": "text", "text": f"Job posting:\n\n{m['job']}\n\nResume:\n\n{m['resume']}\n\nRequirement: {m['requirement']}"}]
    if fam == "suggest":
        ev = lambda xs: "\n".join(f"- {x}" for x in xs) or "(none)"  # noqa: E731
        return [{"type": "text", "text": f"Product: {m['product']}\nSelling point: {m['claim']}\nLabel: {m['label']}\n"
                                         f"Supporting reviews:\n{ev(m['support'])}\nRefuting reviews:\n{ev(m['refute'])}"}]
    raise KeyError(fam)


def material_blocks(item: dict, cand: dict | None = None) -> list[dict]:
    fam, m = item["family"], item["material"]
    cand = cand if cand is not None else item.get("candidate")
    if fam in ("review", "qc", "claim", "suggest"):
        return context_blocks(item) + [{"type": "text", "text": candidate_text("review" if fam == "qc" else fam, cand)}]
    if fam == "regulator":
        return [{"type": "text", "text": ("Ad as described:\n" if m["regime"] == "UK-ASA" else "广告描述：\n") + m["ad"]}]
    if fam == "jv":
        return [{"type": "text", "text": f"Question:\n{m['question']}\n\nReference answer:\n{m['reference']}\n\nGenerated answer:\n{m['answer']}"}]
    if fam == "summeval":
        return [{"type": "text", "text": f"Article:\n{m['article']}\n\nSummary:\n{m['summary']}"}]
    if fam == "mqm":
        return [{"type": "text", "text": f"Source (Chinese):\n{m['source']}\n\nTranslation (English):\n{m['translation']}"}]
    raise KeyError(fam)


def request(item: dict, version: str = "v2", wording: str = "r0", swap: bool = False, cand: dict | None = None) -> tuple[str, list[dict], dict]:
    """(system prompt, user content, output schema) for one item."""
    fam = item["family"]
    if fam in BINARY:
        system = system_binary(fam, version, wording, swap)
        if fam == "review":
            system += "\n\nPolicy library (" + item["material"]["jurisdiction"] + "):\n\n" + library_text(item["material"]["jurisdiction"])
        return system, material_blocks(item, cand), schema_binary(fam, version, swap)
    if fam == "regulator":
        system = REGULATOR_SYSTEM[item["material"]["regime"]]
        if item["material"]["regime"] == "CN":
            system += "\n\n法规条款：\n\n" + library_text("CN")
        return system, material_blocks(item), REGULATOR_SCHEMA
    if fam == "jv":
        return JV_SYSTEM, material_blocks(item), JV_SCHEMA
    if fam == "summeval":
        return SUMMEVAL_SYSTEM.format(definition=SUMMEVAL_DEF[item["dimension"]]), material_blocks(item), SUMMEVAL_SCHEMA
    if fam == "mqm":
        return MQM_SYSTEM, material_blocks(item), MQM_SCHEMA
    raise KeyError(fam)


def verdict_of(item: dict, version: str, output: dict):
    """The judge's answer in the item's truth vocabulary (pass/fail, a score, or a class)."""
    fam = item["family"]
    if output is None:
        return None
    if fam in BINARY:
        return verdict_from_checks(fam, output["checks"]) if version in ("v3", "v4") else output["verdict"]
    if fam == "regulator":
        return "fail" if output["verdict"] == "breach" else "pass"
    if fam == "jv":
        return float(output["score"])
    if fam == "summeval":
        return int(output["score"])
    if fam == "mqm":
        return output["verdict"]
    raise KeyError(fam)


# ------------------------------------------------------------------------------------------- candidate-side changes
FILLER = {
    "en": (" This was prepared by going through the material one element at a time, comparing each part with every relevant point, "
           "and re-reading the final wording before it was submitted. Each step was repeated so that nothing would be overlooked, "
           "and the result above reflects that complete pass through the material from beginning to end."),
    "zh": "以上内容是把材料逐项过了一遍之后写成的：每一部分都和相关的每一点对照过，提交前又把最后的措辞通读了一遍。每一步都重复做过，避免遗漏，上面的结果反映的是对材料从头到尾的完整梳理。",
}
ASSERT = {"en": " I have double-checked every point against the material and I am fully confident this is correct.",
          "zh": "以上结论已逐项核对原文，确认无误。"}
FREE_TEXT = {"review": "notes", "claim": "reasoning", "suggest": "advice"}


def perturb_candidate(item: dict, how: str) -> dict:
    """The same candidate with content-free text added to its free-text field: 'verbose' adds a long passage
    about how carefully it was prepared, 'assertive' adds one sentence of assurance. Neither changes what
    the candidate claims about the material, so its right answer stays the same."""
    import copy

    cand = copy.deepcopy(item["candidate"])
    lang = "zh" if item["lang"] == "zh" else "en"
    add = FILLER[lang] if how == "verbose" else ASSERT[lang]
    key = FREE_TEXT[item["family"]]
    cand[key] = (cand.get(key, "") or "").rstrip() + add
    return cand
