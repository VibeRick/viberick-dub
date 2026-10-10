"""Gemini text calls on Vertex (project viberick credit) with retry, JSON mode and a cost ledger."""
import json
import random
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


def _call(contents, cfg: types.GenerateContentConfig, tries: int = 8):
    for i in range(tries):
        try:
            with _gate:
                resp = client().models.generate_content(model=config.TEXT_MODEL, contents=contents, config=cfg)
            _record(config.TEXT_MODEL, resp)
            if not resp.text:
                raise RuntimeError("empty model response")
            return resp
        except Exception as e:  # noqa: BLE001  429/500 from the shared pool, empty output
            if i == tries - 1 or str(e).startswith("400"):
                raise
            time.sleep(min(60, 2 ** i) * (0.5 + random.random()))


def json_call(prompt: str, schema: dict, parts: list | None = None, thinking: str = "low") -> dict:
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return json.loads(_call([*(parts or []), prompt], cfg).text)


def text_call(prompt: str, parts: list | None = None, thinking: str = "low") -> str:
    cfg = types.GenerateContentConfig(max_output_tokens=65536,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return _call([*(parts or []), prompt], cfg).text
