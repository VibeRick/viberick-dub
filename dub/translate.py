"""Dubbing translation: every line must be speakable inside its time slot.

CPS = characters per second of the TTS voice at natural speed. Values measured on gemini-3.8-flash-tts
(preset voices 2026-10-08; replicated voice spot-check 2026-10-10: ko 6.1, en 17.1, ja 6.2)."""
from concurrent.futures import ThreadPoolExecutor

from . import config, gem

CPS = {"en": 15.1, "ja": 6.2, "zh-Hans": 5.2, "ko": 7.0}
BATCH = 40
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
    "required": ["id", "text"]}}}, "required": ["lines"]}


def budget(lang: str, seconds: float) -> int:
    return max(4, int(CPS.get(lang, 14.0) * seconds * 0.95))


def _batch(batch: list[dict], src: str, lang: str, brief: dict, prev: list[str]) -> list[str]:
    lines = "\n".join(f'{{"id":{u["id"]},"max_chars":{budget(lang, u["slot"])},"src":{u["text"]!r}}}'
                      for u in batch)
    terms = "\n".join(f"- {t['source']}: {t['rule']}" for t in brief.get("terms", []))
    out = gem.json_call(
        f"You are a professional dubbing translator. Translate each {config.LANGS[src]} line into "
        f"{config.LANGS[lang]} for a voice-over that replaces the original speech.\n"
        f"Topic: {brief.get('summary', '')}\nSpeaker: {brief.get('speaker_style', '')}\nTerms:\n{terms}\n"
        f"Previous lines (continuity): {' '.join(prev[-3:]) or '(start)'}\n\nRules:\n"
        "- Use between 75% and 100% of max_chars (100% = the slot at natural speed). Under 75% leaves dead "
        "air while the speaker is visibly talking; over 100% will not fit.\n"
        "- Reach the length by translating fully, never by adding things the source does not say. If the "
        "meaning is longer than max_chars, cut redundancy and fillers first, never the point.\n"
        "- Drop spoken fillers and false starts unless they carry meaning. Keep the friendly, direct tone.\n"
        "- Consecutive lines may be fragments of one sentence; they must read naturally when joined.\n"
        "- Numbers, URLs and code as a speaker would say them.\n"
        "- Output every id exactly once, same order.\n\nLines:\n" + lines, SCHEMA)
    got = {l["id"]: l["text"].strip() for l in out["lines"]}
    return [got.get(u["id"], "") for u in batch]


def translate(units: list[dict], src: str, lang: str, brief: dict) -> list[str]:
    batches = [units[i:i + BATCH] for i in range(0, len(units), BATCH)]
    with ThreadPoolExecutor(max(1, len(batches))) as ex:
        parts = list(ex.map(lambda ib: _batch(ib[1], src, lang, brief,
                                              [u["text"] for u in batches[ib[0] - 1]] if ib[0] else []),
                            enumerate(batches)))
    out = [t for p in parts for t in p]
    for i, t in enumerate(out):
        if not t and units[i]["text"].strip():
            out[i] = _batch([units[i]], src, lang, brief, out[max(0, i - 3):i])[0]
    return out


def shorten(src_text: str, text: str, lang: str, seconds: float, ratio: float) -> str:
    target = max(4, int(len(text) * 0.93 / ratio))
    return gem.json_call(
        f"This {config.LANGS[lang]} dubbing line runs {ratio:.0%} of its {seconds:.1f}s slot. Rewrite it in at "
        f"most {target} characters. Keep the point of the original and the tone; drop redundancy, never "
        f"meaning.\nOriginal: {src_text}\nCurrent: {text}",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})["text"].strip()
