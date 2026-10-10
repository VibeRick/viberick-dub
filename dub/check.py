"""Gemini listens to one dubbed clip and says whether it is the right line in the right language."""
from pathlib import Path

from google.genai import types

from . import config, gem

SCHEMA = {"type": "object", "properties": {"heard": {"type": "string"}, "language_ok": {"type": "boolean"},
                                           "content_ok": {"type": "boolean"}, "issue": {"type": "string"}},
          "required": ["heard", "language_ok", "content_ok", "issue"]}


def check(clip: Path, text: str, lang: str) -> dict:
    return gem.json_call(
        f"Listen to this dubbing clip. Expected language: {config.LANGS[lang]}. Expected line: {text!r}\n"
        "heard: what is actually said. language_ok: spoken in the expected language. content_ok: says the "
        "expected line (contractions, number formats and punctuation are fine; extra words or sounds, spoken "
        "instructions, missing clauses, garbled or truncated speech are not). issue: '' if fine.",
        SCHEMA, parts=[types.Part.from_bytes(data=clip.read_bytes(), mime_type="audio/wav")])
