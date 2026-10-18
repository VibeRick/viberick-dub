"""Map one text's characters onto another's timed characters (Levenshtein alignment).

Used to give Gemini's corrected transcript the timing of Chirp 3's words: Chirp is accurate in time,
Gemini is accurate in text."""
import re

from rapidfuzz.distance import Levenshtein

_KEEP = re.compile(r"[^\W_]")   # letters and digits of any script (Devanagari, Arabic, Thai…), not just CJK + Latin


def norm_chars(text: str) -> list[str]:
    return [c for c in text.lower() if _KEEP.match(c)]


def timed_chars(units: list[dict]) -> tuple[str, list[float]]:
    chars, times = [], []
    for u in units:
        cs = norm_chars(u["text"])
        dur = max(0.0, (u["end"] or u["start"]) - u["start"])
        for i, c in enumerate(cs):
            chars.append(c)
            times.append(u["start"] + dur * i / max(1, len(cs)))
    return "".join(chars), times


def _map(a: str, b: str) -> dict[int, int]:
    m = {}
    for tag, sa, sb, da, db in Levenshtein.opcodes(a, b):
        if tag in ("equal", "replace"):
            for k in range(sa, sb):
                m[k] = da + min(k - sa, db - da - 1)
    return m


def retime(lines: list[str], words: list[dict]) -> list[dict]:
    ref, ref_t = timed_chars([{"start": w["start"], "end": w["end"], "text": w["w"]} for w in words])
    word_end = {}
    pos = 0
    for w in words:
        n = len(norm_chars(w["w"]))
        for k in range(pos, pos + n):
            word_end[k] = w["end"]
        pos += n
    owner, chars = [], []
    for li, line in enumerate(lines):
        for c in norm_chars(line):
            chars.append(c)
            owner.append(li)
    m = _map("".join(chars), ref)
    cues: list[dict] = []
    for li, line in enumerate(lines):
        idx = [k for k in range(len(chars)) if owner[k] == li and k in m]
        if not idx:
            if cues:
                cues[-1]["text"] = f"{cues[-1]['text']} {line}".strip()
            continue
        a, b = m[idx[0]], m[idx[-1]]
        cues.append({"start": round(ref_t[a], 3), "end": round(word_end.get(b, ref_t[b]), 3), "text": line})
    return cues
