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


CONTINUOUS = 0.35   # source gap below this = the speaker did not pause
BREATH = 1.0        # a mid-sentence source pause shorter than this is a breath, not a beat
FLOW_GAP = 0.12     # silence between two separately synthesized lines that should sound continuous
_SENTENCE_END = re.compile(r"[.!?。！？…]['\"”’」』)]*\s*$")


def flow_gaps(units: list[dict], from_take: list[bool], repaired: list[bool],
              texts: list[str] | None = None) -> list[float | None]:
    """Per line: None = anchor to its source start; else place right after the previous clip with this gap.
    A line flows on when the speaker did not pause, or only took a breath in the middle of the dubbed
    sentence (Korean breath pauses split English sentences otherwise). Sentence ends re-anchor to the
    video. mix.place caps how early a flowing line may start."""
    out: list[float | None] = [None]
    for i in range(1, len(units)):
        gap = units[i]["start"] - units[i - 1]["end"]
        mid_sentence = texts is not None and not _SENTENCE_END.search(texts[i - 1].strip())
        if gap >= CONTINUOUS and not (mid_sentence and gap < BREATH):
            out.append(None)
        elif from_take[i] and not repaired[i] and not repaired[i - 1]:
            out.append(0.0)   # same take: the clip edges already carry the natural pause
        else:
            out.append(FLOW_GAP)
    return out
