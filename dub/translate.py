"""Dubbing translation: every line must be speakable inside its time slot.

CPS = characters per second of the cloned voice at natural speed, measured 2026-10-10 on 204 lines of
Fty2sz3dBwU (speech only, edge silence excluded). The old preset-voice table (en 15.1, ja 6.2, zh 5.2) was
11–24 % too slow, so lines came out short and the dub had 2.5–4× the source's pauses."""
from concurrent.futures import ThreadPoolExecutor

from . import config, gem

CPS = {"en": 18.7, "ja": 6.9, "zh-Hans": 5.9, "ko": 6.5}
BATCH = 40
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
    "required": ["id", "text"]}}}, "required": ["lines"]}


def budget(lang: str, seconds: float) -> int:
    return max(4, int(CPS.get(lang, 14.0) * seconds))


def _batch(batch: list[dict], src: str, lang: str, brief: dict, prev: list[str]) -> list[str]:
    lines = "\n".join(f'{{"id":{u["id"]},"max_chars":{budget(lang, u["slot"])},"src":{u["text"]!r}}}'
                      for u in batch)
    terms = "\n".join(f"- {t['source']}: {t['rule']}" for t in brief.get("terms", []))
    out = gem.json_call(
        f"You are a professional dubbing translator. Translate each {config.LANGS[src]} line into "
        f"{config.LANGS[lang]} for a voice-over that replaces the original speech.\n"
        f"Topic: {brief.get('summary', '')}\nSpeaker: {brief.get('speaker_style', '')}\nTerms:\n{terms}\n"
        f"Previous lines (continuity): {' '.join(prev[-3:]) or '(start)'}\n\nRules:\n"
        "- Say it the way this speaker would naturally say it in the target language. Never exceed max_chars "
        "(100% = the slot at natural speed); aim for 80-100% by translating fully, but never pad with words the "
        "speaker would not say (no empty intensifiers). A natural line slightly short beats a padded one.\n"
        "- If the meaning is longer than max_chars, cut redundancy and fillers first, never the point.\n"
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


UNDERFILL = 0.6


def _chars(text: str, lang: str) -> int:
    return len(text) if lang == "en" else len(text.replace(" ", ""))


def expand(units: list[dict], texts: list[str], src: str, lang: str, brief: dict) -> list[str]:
    """Second pass for lines Gemini left short (measured: median fill 67–78 % despite the 85 % rule).
    A short line leaves the speaker's mouth moving over silence; rewrite it fuller from the source."""
    short = [(u, t) for u, t in zip(units, texts) if t and _chars(t, lang) < UNDERFILL * budget(lang, u["slot"])]
    if not short:
        return texts
    lines = "\n".join(f'{{"id":{u["id"]},"target_chars":{int(budget(lang, u["slot"]) * 0.85)},'
                      f'"src":{u["text"]!r},"current":{t!r}}}' for u, t in short)
    out = {}
    for i in range(0, len(short), BATCH):
        chunk = "\n".join(lines.splitlines()[i:i + BATCH])
        got = gem.json_call(
            f"These {config.LANGS[lang]} dubbing lines are too short for the time the speaker talks, so the dub "
            f"goes silent while the speaker's mouth still moves. Rewrite each to about target_chars characters "
            f"(count them). Translate the {config.LANGS[src]} source more fully: keep its nuance, hedges and "
            "connectives, and use natural spoken phrasing. Never add facts, examples or opinions the source does "
            "not have, and no empty intensifiers (truly, really, dedicated, focused, practically). If a line "
            f"cannot grow naturally, return it unchanged. Keep terms consistent: {[t['source'] for t in brief.get('terms', [])]}.\n"
            "Output every id once.\n\nLines:\n" + chunk, SCHEMA)
        out.update({l["id"]: l["text"].strip() for l in got["lines"]})
    res = list(texts)
    for k, u in enumerate(units):
        new = out.get(u["id"], "")
        if new and _chars(texts[k], lang) < _chars(new, lang) <= budget(lang, u["slot"]) * 1.05:
            res[k] = new
    return res
