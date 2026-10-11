"""Gemini text calls on Vertex (project viberick credit) with retry, JSON mode and a cost ledger."""
import json
import random
import re
import sys
import threading
import time

from google import genai
from google.genai import types

from . import config

# USD per 1M tokens (in, out). Estimates for the cost slide only.
PRICE = {config.TEXT_MODEL: (0.75, 3.75)}
LEDGER: dict[str, dict] = {}
_lock = threading.Lock()
_gate = threading.BoundedSemaphore(24)
_client = None


def client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, api_key=config.gemini_key())
    return _client


def _record(model: str, resp) -> None:
    u = getattr(resp, "usage_metadata", None)
    if not u:
        return
    with _lock:
        row = LEDGER.setdefault(model, {"calls": 0, "in": 0, "out": 0})
        row["calls"] += 1
        row["in"] += u.prompt_token_count or 0
        row["out"] += (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


def cost() -> float:
    return round(sum(r["in"] / 1e6 * PRICE.get(m, (1, 10))[0] + r["out"] / 1e6 * PRICE.get(m, (1, 10))[1]
                     for m, r in LEDGER.items()), 4)


def _status_code(error: Exception) -> int | None:
    for value in (getattr(error, "code", None), getattr(error, "status_code", None),
                  getattr(getattr(error, "response", None), "status_code", None)):
        if isinstance(value, int):
            return value
    match = re.match(r"^(?:HTTP\s+)?(\d{3})(?:\D|$)", str(error))
    return int(match[1]) if match else None


def _call(contents, cfg: types.GenerateContentConfig, tries: int = 8, parse=None):
    if tries < 1:
        raise ValueError("tries must be positive")
    for i in range(tries):
        try:
            with _gate:
                resp = client().models.generate_content(model=config.TEXT_MODEL, contents=contents, config=cfg)
            _record(config.TEXT_MODEL, resp)
            if not resp.text:
                raise RuntimeError("empty model response")
            return parse(resp.text) if parse else resp
        except Exception as e:  # noqa: BLE001  429/500 from the shared pool, empty output
            if i == tries - 1 or _status_code(e) in {400, 401, 403, 404}:
                raise
            print(f"gemini retry {i + 1}/{tries}: status={_status_code(e) or 'unavailable'} "
                  f"type={type(e).__name__}", file=sys.stderr, flush=True)
            time.sleep(min(60, 2 ** i) * (0.5 + random.random()))


def json_call(prompt: str, schema: dict, parts: list | None = None, thinking: str = "low") -> dict:
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return _call([*(parts or []), prompt], cfg, parse=json.loads)


def text_call(prompt: str, parts: list | None = None, thinking: str = "low") -> str:
    cfg = types.GenerateContentConfig(max_output_tokens=65536,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return _call([*(parts or []), prompt], cfg).text
