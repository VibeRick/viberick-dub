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
    return [lang for lang in config.DEFAULT_LANGS if lang != src]


MAX_UNIT_SEC = 14.0   # longest sentence unit; longer runs split at a fragment boundary
MAX_JOIN_GAP = 1.5    # a pause longer than this ends the unit even mid-sentence


def _ends_sentence(text: str) -> bool:
    t = text.strip()
    return bool(_SENTENCE_END.search(t)) or t.endswith(("다", "요", "죠", "까"))


def sentences(cues: list[dict]) -> list[dict]:
    """Merge breath-sized fragments into sentences. Korean puts the verb last, so a fragment like
    "SEO, AEO, GEO" cannot be translated on its own; the dub must be built a sentence at a time."""
    out: list[dict] = []
    for c in cues:
        if out:
            cur = out[-1]
            if (not c.get("hard_anchor") and not c.get("scene_cut")
                    and cur.get("spk") == c.get("spk") and not _ends_sentence(cur["text"])
                    and c["start"] - cur["end"] < MAX_JOIN_GAP
                    and c["end"] - cur["start"] <= MAX_UNIT_SEC):
                out[-1] = {**cur, "end": c["end"], "text": f"{cur['text']} {c['text']}",
                           "scene_cuts_inside": cur.get("scene_cuts_inside", []) + c.get("scene_cuts_inside", [])}
                continue
        out.append(dict(c))
    return out


def make_units(cues: list[dict], duration: float) -> list[dict]:
    cues = sentences(cues)
    out = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else duration
        slot = max(0.6, min(nxt, c["end"] + 0.8, duration) - c["start"])
        out.append({"id": i, "start": c["start"], "end": c["end"], "slot": round(slot, 3), "text": c["text"],
                    **({"spk": c["spk"]} if "spk" in c else {}),
                    **{k: c[k] for k in ("hard_anchor", "scene_cut", "scene_cuts_before", "scene_cuts_inside") if k in c}})
    return out


CONTINUOUS = 0.35   # source gap below this = the speaker did not pause
BREATH = 1.0        # a mid-sentence source pause shorter than this is a breath, not a beat
FLOW_GAP = 0.12     # silence between two separately synthesized lines that should sound continuous
_SENTENCE_END = re.compile(r"[.!?。！？…।॥؟۔]['\"”’」』)]*\s*$")


def flow_gaps(units: list[dict], from_take: list[bool], repaired: list[bool],
              texts: list[str] | None = None) -> list[float | None]:
    """Per line: None = anchor to its source start; else place right after the previous clip with this gap.
    A line flows on when the speaker did not pause, or only took a breath in the middle of the dubbed
    sentence (Korean breath pauses split English sentences otherwise). Sentence ends re-anchor to the
    video. mix.place caps how early a flowing line may start."""
    if not units:
        return []
    out: list[float | None] = [None]
    for i in range(1, len(units)):
        if (units[i].get("spk") != units[i - 1].get("spk")
                or units[i].get("hard_anchor") or units[i].get("scene_cut")):
            out.append(None)
            continue
        gap = units[i]["start"] - units[i - 1]["end"]
        mid_sentence = texts is not None and not _SENTENCE_END.search(texts[i - 1].strip())
        if gap >= CONTINUOUS and not (mid_sentence and gap < BREATH):
            out.append(None)
        elif from_take[i] and not repaired[i] and not repaired[i - 1]:
            out.append(0.0)   # same take: the clip edges already carry the natural pause
        else:
            out.append(FLOW_GAP)
    return out


def pick_targets(requested: list[str] | None, src: str) -> list[str]:
    """Requested languages minus the detected source (the UI cannot know the source before transcription)."""
    langs = [lang for lang in dict.fromkeys(requested or []) if lang != src and lang in config.LANGS]
    return langs or targets_for(src)


_NOISE = re.compile(r"https?://\S+|www\.\S+|#\S+|@\S+")


def guess_source(info: dict) -> str:
    """Language for Chirp before any audio is heard: title counted three times, description once,
    links/hashtags/handles removed (they are Latin text in any language and tipped Korean videos to en)."""
    title = _NOISE.sub(" ", info.get("title") or "")
    desc = _NOISE.sub(" ", info.get("description") or "")
    return detect_language(f"{title} {title} {title} {desc}")
