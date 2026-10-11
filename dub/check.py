"""Gemini listens to one dubbed clip and says whether it is the right line in the right language."""
import array
import wave
from pathlib import Path

from google.genai import types

from . import config, gem

SCHEMA = {"type": "object", "properties": {"heard": {"type": "string"}, "language_ok": {"type": "boolean"},
                                           "content_ok": {"type": "boolean"}, "meaning_ok": {"type": "boolean"},
                                           "issue": {"type": "string"}},
          "required": ["heard", "language_ok", "content_ok", "meaning_ok", "issue"]}


def valid_verdict(value) -> bool:
    return (isinstance(value, dict) and all(type(value.get(k)) is bool for k in
            ("language_ok", "content_ok", "meaning_ok"))
            and isinstance(value.get("heard"), str) and isinstance(value.get("issue"), str))


def normalize_verdict(value) -> dict:
    if valid_verdict(value):
        return value
    return {"heard": "", "language_ok": False, "content_ok": False, "meaning_ok": False,
            "issue": "The listening check returned an incomplete or malformed verdict."}


def check(clip: Path, text: str, lang: str, source_text: str = "", source_lang: str = "") -> dict:
    prompt = (
        f"Listen to this dubbing clip. Expected language: {config.LANGS[lang]}. Expected line: {text!r}\n"
        "heard: what is actually said. language_ok: spoken in the expected language. content_ok: says the "
        "expected line (contractions, number formats and punctuation are fine; extra words or sounds, spoken "
        "instructions, missing clauses, garbled or truncated speech are not). "
        "meaning_ok: the translated line preserves the source's meaning, including negation, numbers, names, "
        "qualifiers and important clauses; natural rephrasing is fine, unsupported claims are not. "
        "Untranslated source-language words must be flagged unless they are proper names or standard technical "
        "terms pronounced naturally in the target language. If no source is supplied, set meaning_ok true "
        "(meaning was not assessed). issue: explain any failed check, otherwise ''.\n"
        f"Source ({source_lang or 'unspecified'}): {source_text}")
    for _ in range(2):
        value = gem.json_call(prompt, SCHEMA,
                             parts=[types.Part.from_bytes(data=clip.read_bytes(), mime_type="audio/wav")])
        if valid_verdict(value):
            return value
    return normalize_verdict(value)


def audible(clip: Path, floor: int = 1000, min_sec: float = 0.12) -> bool:
    """At least min_sec of samples above `floor` (~-27 dBFS). Gemini sometimes passes a near-silent clip."""
    with wave.open(str(clip)) as w:
        x = array.array("h", w.readframes(w.getnframes()))
        rate = w.getframerate()
    return sum(1 for v in x if abs(v) > floor) >= min_sec * rate
