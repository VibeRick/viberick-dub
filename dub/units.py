"""Cues → dubbing units with time slots; crude script-based source language detection."""
import re

from . import config


def detect_language(text: str) -> str:
    counts = {"ko": len(re.findall(r"[가-힣]", text)), "ja": len(re.findall(r"[぀-ヿ]", text)),
              "zh-Hans": len(re.findall(r"[一-鿿]", text)), "en": len(re.findall(r"[A-Za-z]", text)) / 4}
    if counts["ja"] > 0 and counts["ja"] >= counts["ko"]:
        return "ja"   # kana only appears in Japanese
    return max(counts, key=counts.get)


def targets_for(src: str) -> list[str]:
    return [lang for lang in config.LANGS if lang != src]


def make_units(cues: list[dict], duration: float) -> list[dict]:
    out = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else duration
        slot = max(0.6, min(nxt, c["end"] + 0.8, duration) - c["start"])
        out.append({"id": i, "start": c["start"], "end": c["end"], "slot": round(slot, 3), "text": c["text"]})
    return out
