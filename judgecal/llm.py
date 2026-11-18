"""Calling the judge model: one client, a resumable store of answers, and Message Batches (half price).

Every judgment in this project is a single request with a JSON answer, so the runner is simple: build all
requests of a stage, skip the ones already answered in the stage's store file, send the rest as one or more
batches, write each answer to the store as it comes back. An interrupted run carries on from the store and
from the journal of batches already submitted, so nothing is paid for twice.

The API key is read from a file (EVAL_ENV_FILE, default .env in the project folder), never from the shell
environment, so a run cannot pick up credentials that belong to other tools. The key is never printed or
stored. Adapted from the batch pool in creator-skills (same author, MIT).
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-haiku-5-5"      # cheapest current model; the judge under test
EFFORT = "medium"               # the model's default
MAX_TOKENS = 8000               # room for thinking plus a short JSON verdict
# List prices per token (USD), prompts up to 100K tokens. Other models are listed for the costed comparison.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10 / 1e6, "output": 0.50 / 1e6},
    "claude-sonnet-5-5": {"input": 2.00 / 1e6, "output": 10.00 / 1e6},
}
BATCH_DISCOUNT = 0.5
BATCH_CHUNK = 1500              # requests per batch
LIVE_BELOW = 20                 # fewer requests than this go out as ordinary calls


def _read_key() -> str:
    env_file = Path(os.environ.get("EVAL_ENV_FILE") or (ROOT / ".env"))
    if not env_file.is_absolute():
        env_file = (ROOT / env_file).resolve()
    if not env_file.exists():
        raise SystemExit(f"API key file not found: {env_file}. Put a line ANTHROPIC_API_KEY=... in .env or set EVAL_ENV_FILE.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("ANTHROPIC_API_KEY missing in the key file")


@lru_cache(maxsize=1)
def client():
    for k in [k for k in os.environ if k.startswith("ANTHROPIC_")]:
        del os.environ[k]
    import anthropic

    return anthropic.Anthropic(api_key=_read_key(), base_url="https://api.anthropic.com", max_retries=4)


def params(system: str, content, schema: dict, model: str = MODEL, effort: str = EFFORT, max_tokens: int = MAX_TOKENS) -> dict:
    """One judging request. content is the user turn: a string or a list of content blocks (text, image)."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }


def cost_of(usage: dict, model: str, batch: bool) -> float:
    p = PRICES[model]
    full = usage.get("input_tokens", 0) * p["input"] + usage.get("output_tokens", 0) * p["output"]
    return full * BATCH_DISCOUNT if batch else full


def _record(key: str, message, batch: bool) -> dict:
    text = "".join(b.text for b in message.content if b.type == "text").strip()
    data, err = None, None
    tool_turn = message.stop_reason == "tool_use"
    if message.stop_reason not in ("end_turn", "tool_use"):
        err = f"stopped: {message.stop_reason}"
    if not tool_turn:
        try:
            data = json.loads(text) if text else None
        except json.JSONDecodeError as e:
            err = err or f"not valid JSON: {e}"
        if data is None and err is None:
            err = "no text in the answer"
    u = message.usage
    usage = {"input_tokens": (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
             + (getattr(u, "cache_read_input_tokens", 0) or 0), "output_tokens": u.output_tokens or 0}
    rec = {"key": key, "output": data, "error": err, "model": message.model, "usage": usage, "stop_reason": message.stop_reason,
           "pricing": "batch" if batch else "standard", "cost_usd": round(cost_of(usage, _price_model(message.model), batch), 8)}
    if tool_turn:   # an agent turn that asks for tools: keep the content to continue the conversation
        rec["content"] = [b.model_dump(mode="json", exclude_none=True) for b in message.content]
    return rec


def _price_model(name: str) -> str:
    for m in PRICES:
        if name.startswith(m):
            return m
    raise KeyError(f"no price listed for {name}")


def load_store(path: Path) -> dict[str, dict]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error"):
                    out[r["key"]] = r
    return out


def run(requests: dict[str, dict], store: Path, log=print, batch: bool = True) -> dict[str, dict]:
    """Answers every request not yet in the store and returns all stored answers for the given keys.

    requests maps a stable key (stage|item|variant|repeat) to request params. Answers are appended to the
    store (JSON lines). A request that fails three times is stored with its error and counted by the scorer.
    """
    store.parent.mkdir(parents=True, exist_ok=True)
    done = load_store(store)
    todo = {k: p for k, p in requests.items() if k not in done}
    if todo:
        log(f"{store.name}: {len(requests) - len(todo)} answers on file, {len(todo)} to ask")
        if batch and len(todo) >= LIVE_BELOW:
            _run_batches(todo, store, log)
        else:
            _run_live(todo, store, log)
        done = load_store(store)
    missing = [k for k in requests if k not in done]
    if missing:
        log(f"{store.name}: {len(missing)} requests have no usable answer (kept as errors)")
    return {k: done[k] for k in requests if k in done}


def _append(store: Path, rec: dict) -> None:
    with store.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _run_live(todo: dict[str, dict], store: Path, log) -> None:
    c = client()

    def one(item):
        key, p = item
        for attempt in range(3):
            try:
                return _record(key, c.messages.create(**p), batch=False)
            except Exception as e:  # stored as a failure after three tries
                err = f"{type(e).__name__}: {e}"
                time.sleep(2 * (attempt + 1))
        return {"key": key, "output": None, "error": err, "usage": {}, "pricing": "standard", "cost_usd": 0.0}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for rec in ex.map(one, todo.items()):
            _append(store, rec)


def _run_batches(todo: dict[str, dict], store: Path, log, poll: float = 20.0) -> None:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    c = client()
    journal = store.with_suffix(".journal.jsonl")
    submitted: dict[str, tuple[str, str]] = {}   # key -> (batch id, custom id)
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                submitted[e["key"]] = (e["batch"], e["custom_id"])
    tries = {k: 0 for k in todo}
    pending = dict(todo)
    while pending:
        # 1) collect answers of batches submitted earlier (also after an interrupted run)
        by_batch: dict[str, dict[str, str]] = {}
        for k in list(pending):
            if k in submitted:
                b, cid = submitted[k]
                by_batch.setdefault(b, {})[cid] = k
        for b, cids in by_batch.items():
            t0 = time.time()
            while True:
                info = c.messages.batches.retrieve(b)
                if info.processing_status == "ended":
                    break
                time.sleep(poll)
            n_ok = 0
            for r in c.messages.batches.results(b):
                k = cids.get(r.custom_id)
                if k is None or k not in pending:
                    continue
                if r.result.type == "succeeded":
                    rec = _record(k, r.result.message, batch=True)
                    if not rec["error"]:
                        _append(store, rec)
                        pending.pop(k)
                        n_ok += 1
                        continue
                tries[k] += 1
            waited = (time.time() - t0) / 60
            log(f"  batch {b[-8:]}: {n_ok}/{len(cids)} answers stored" + (f" after {waited:.1f} min" if waited > 0.2 else ""))
            for k in cids.values():
                submitted.pop(k, None)   # anything still pending from this batch is sent again
        # 2) send what is still open
        give_up = [k for k in pending if tries[k] >= 3]
        for k in give_up:
            _append(store, {"key": k, "output": None, "error": "no usable answer after three tries", "usage": {},
                            "pricing": "batch", "cost_usd": 0.0})
            pending.pop(k)
        keys = [k for k in pending if k not in submitted]
        for i in range(0, len(keys), BATCH_CHUNK):
            chunk = keys[i:i + BATCH_CHUNK]
            reqs = [Request(custom_id=f"r{j:05d}", params=MessageCreateParamsNonStreaming(**pending[k])) for j, k in enumerate(chunk)]
            batch = c.messages.batches.create(requests=reqs)
            with journal.open("a", encoding="utf-8", newline="\n") as f:
                for j, k in enumerate(chunk):
                    f.write(json.dumps({"key": k, "batch": batch.id, "custom_id": f"r{j:05d}"}) + "\n")
                    submitted[k] = (batch.id, f"r{j:05d}")
            log(f"  sent batch {batch.id[-8:]} with {len(chunk)} requests")


def total_cost(store: Path) -> dict:
    """Calls, tokens and cost of everything in a store file, failed tries excluded (they are not billed twice
    in the store; the journal keeps the batch ids for an audit against the billing page)."""
    calls = inp = out = 0
    usd = 0.0
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("usage"):
                    calls += 1
                    inp += r["usage"].get("input_tokens", 0)
                    out += r["usage"].get("output_tokens", 0)
                    usd += r.get("cost_usd", 0.0)
    return {"calls": calls, "input_tokens": inp, "output_tokens": out, "cost_usd": round(usd, 4)}
