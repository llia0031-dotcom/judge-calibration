"""Loading the judging items (public ones from data/items, the ones whose text is not redistributed from private/items)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ.get("JC_PRIVATE", ROOT / "private"))
FAMILIES = ("review", "claim", "suggest", "regulator", "jv", "summeval", "mqm")


def h(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def load(family: str) -> list[dict]:
    for d in (PRIVATE / "items", ROOT / "data" / "items"):
        p = d / f"{family}.jsonl"
        if p.exists():
            return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return []


def load_all(families=FAMILIES) -> list[dict]:
    out = []
    for f in families:
        out += load(f)
    return out
