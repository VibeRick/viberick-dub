"""SRT writer: long lines split at punctuation into readable cues, timed by character share."""
import re

CJK = {"ja", "zh-Hans"}


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces = [p for p in re.split(r"(?<=[.!?。！？,，、;:])\s*", text) if p]
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip() if cur and not re.match(r"[぀-鿿]", p) else cur + p
    out.append(cur)
    final = []
    for c in out:
        while len(c) > limit * 1.3:
            cut = c.rfind(" ", 0, limit) if " " in c[:limit] else limit
            final.append(c[:cut].strip())
            c = c[cut:].strip()
        final.append(c)
    return [f for f in final if f]


def srt(units: list[dict], texts: list[str], lang: str) -> str:
    limit = 22 if lang in CJK else 42
    blocks, n = [], 1
    for u, t in zip(units, texts):
        parts = _split(t.strip(), limit)
        total = sum(len(p) for p in parts) or 1
        s = u["start"]
        for p in parts:
            e = s + (u["end"] - u["start"]) * len(p) / total
            blocks.append(f"{n}\n{_ts(s)} --> {_ts(e)}\n{p}\n")
            n += 1
            s = e
    return "\n".join(blocks)
