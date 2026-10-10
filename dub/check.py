"""Gemini listens to one dubbed clip and says whether it is the right line in the right language."""
import array
import wave
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


def audible(clip: Path, floor: int = 1500, min_sec: float = 0.25) -> bool:
    """At least min_sec of samples above `floor` (~-27 dBFS). Gemini sometimes passes a near-silent clip."""
    with wave.open(str(clip)) as w:
        x = array.array("h", w.readframes(w.getnframes()))
        rate = w.getframerate()
    return sum(1 for v in x if abs(v) > floor) >= min_sec * rate
