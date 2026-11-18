"""Rule checks: what can be decided without a model.

A rule check never says a candidate is right. It finds the kinds of error a script can find for certain:
a quote that is not in the material, a figure that is not in the quoted text, a clause id that does not
exist, a structure that contradicts itself. Quote and figure matching is evidence-check's script
(evcheck, MIT), the same one the source projects run; nothing here re-implements it.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from evcheck import _rules as ev

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILES = {"CN": [ROOT / "data" / "policy" / "cn.json"],
                "TikTok": [Path(os.environ.get("JC_PRIVATE", ROOT / "private")) / "policy" / "tiktok.json",
                           ROOT / "data" / "policy" / "tiktok.stub.json"]}


@lru_cache(maxsize=4)
def policy(jurisdiction: str) -> dict:
    """The clause library of one jurisdiction. The TikTok policy text is not redistributed: without the
    private copy the stub (ids, titles, links) is loaded and policy quotes cannot be checked."""
    for p in POLICY_FILES[jurisdiction]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no policy file for {jurisdiction}")


@lru_cache(maxsize=4)
def _clauses(jurisdiction: str) -> dict:
    return {c["id"]: c for c in policy(jurisdiction)["clauses"]}


def _source(name: str, text: str):
    return ev.Source(name, Path(name), text)


def found(text: str, quote: str) -> bool:
    """True if the quote is part of the text (evidence-check's exact or loose match)."""
    return bool(quote.strip()) and _source("s", text).find(quote)[0] is not None


def review_problems(material: dict, cand: dict) -> list[str]:
    """Problems a script can find in an ad review: structure, clause ids, verbatim quotes."""
    probs = []
    clauses = _clauses(material["jurisdiction"])
    if cand.get("decision") not in ("approve", "reject"):
        probs.append("bad_decision")
    if cand.get("decision") == "reject" and not cand.get("violations"):
        probs.append("reject_without_violation")
    if cand.get("decision") == "approve" and cand.get("violations"):
        probs.append("approve_with_violation")
    for v in cand.get("violations", []):
        c = clauses.get(v.get("clause_id", ""))
        if c is None:
            probs.append("unknown_clause")
            continue
        if c["kind"] != "rule":
            probs.append("guidance_cited_as_rule")
        if v.get("ad_quote", "").strip():
            if not found(material["ad_text"], v["ad_quote"]):
                probs.append("ad_quote_not_found")
        elif not v.get("visual_evidence", "").strip():
            probs.append("no_ad_evidence")
        if "policy_quote" in v and "text" in c and not found(c["text"], v["policy_quote"]):
            probs.append("policy_quote_not_found")   # a label without a policy quote (the QC batches) is not checked for one
    return sorted(set(probs))


def claim_problems(material: dict, cand: dict) -> list[str]:
    """Problems a script can find in a 'requirement met' verdict: quotes not in the resume, figures in
    the stated fact that the quotes do not contain."""
    claim = {"id": "x", "text": cand.get("resume_fact", ""),
             "evidence": [{"source": "resume.md", "quote": q} for q in cand.get("quotes", [])]}
    res = ev.check_claim(claim, {"resume.md": _source("resume.md", material["resume"])})
    return [] if res["status"] == "supported" else list(res["problems"])


def suggest_problems(material: dict, cand: dict) -> list[str]:
    """A suggestion has no checkable quotes; only an empty one can be caught by rule."""
    return [] if (cand.get("rewrite", "").strip() or cand.get("advice", "").strip()) else ["empty_suggestion"]


def problems(item: dict) -> list[str]:
    fam = item["family"]
    if fam in ("review", "qc"):
        return review_problems(item["material"], item["candidate"])
    if fam == "claim":
        return claim_problems(item["material"], item["candidate"])
    if fam == "suggest":
        return suggest_problems(item["material"], item["candidate"])
    return []
