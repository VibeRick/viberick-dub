"""Who speaks each line, and which voice speaks it in the dub.

Chirp 3 labels every word with a speaker. Only a speaker who unambiguously matches
the consent recording gets the creator's cloned voice. Every other speaker is cast to a Gemini preset voice:
Gemini listens to a few seconds of that speaker and picks the closest preset."""
import subprocess
from collections import Counter
from itertools import cycle
import math
from pathlib import Path

from google.genai import types

from . import gem

# Gemini TTS preset voices with the style the docs give them (gender as commonly perceived).
PRESETS = {
    "Charon": "male, informative, mid-low", "Puck": "male, upbeat", "Orus": "male, firm", "Fenrir": "male, excitable",
    "Iapetus": "male, clear", "Algieba": "male, smooth", "Sadaltager": "male, knowledgeable, mature",
    "Kore": "female, firm", "Aoede": "female, breezy", "Leda": "female, youthful", "Sulafat": "female, warm",
    "Despina": "female, smooth", "Gacrux": "female, mature", "Zephyr": "female, bright",
}
_ROTATION = ["Charon", "Kore", "Puck", "Aoede", "Orus", "Leda"]


def label_cues(cues: list[dict], words: list[dict]) -> list[dict]:
    out = []
    for c in cues:
        spk = Counter(w.get("spk") for w in words if c["start"] - 0.05 <= w["start"] <= c["end"] + 0.05)
        out.append({**c, "spk": (spk.most_common(1)[0][0] if spk else None) or "1"})
    return out


def talk_time(units: list[dict]) -> Counter:
    t = Counter()
    for u in units:
        t[u.get("spk") or "1"] += u["end"] - u["start"]
    return t


def _verified_owners(order: list[str], scores: dict[str, float], threshold: float,
                     margin: float = 0.05) -> set[str]:
    """Choose an unambiguous best match per recognition chunk, never by airtime.

    Diarization IDs are scoped to chunks: the same owner can have a different ID
    in each chunk. Close candidates within a chunk are deliberately left uncast.
    """
    groups: dict[str, list[tuple[float, str]]] = {}
    for speaker in order:
        score = scores.get(speaker)
        if score is not None and math.isfinite(score):
            chunk = speaker.split(":", 1)[0] if ":" in speaker else "unscoped"
            groups.setdefault(chunk, []).append((score, speaker))
    owners = set()
    for candidates in groups.values():
        candidates.sort(reverse=True)
        score, speaker = candidates[0]
        if score >= threshold and (len(candidates) == 1 or score - candidates[1][0] >= margin):
            owners.add(speaker)
    return owners


def default_cast(units: list[dict], clone: str, consent: bool, verified: set[str] | None = None,
                 *, scores: dict[str, float] | None = None) -> dict[str, str]:
    """Only verified, unambiguous identities receive the clone; unchecked means presets."""
    from . import verify
    order = [s for s, _ in talk_time(units).most_common()]
    owners = set()
    if consent:
        # A legacy verification set contains no ranking evidence. Ties fail closed.
        evidence = scores if scores is not None else {s: 1.0 for s in (verified or set())}
        owners = _verified_owners(order, evidence, verify.THRESHOLD)
    presets = cycle(_ROTATION)
    return {s: clone if s in owners else next(presets) for s in order}


def _sample(vocals: Path, units: list[dict], spk: str, out: Path, sec: float = 8.0) -> Path | None:
    segs, total = [], 0.0
    for u in sorted((u for u in units if u.get("spk") == spk), key=lambda u: u["start"] - u["end"]):
        segs.append((u["start"], min(u["end"], u["start"] + sec - total)))
        total += segs[-1][1] - segs[-1][0]
        if total >= sec:
            break
    if not segs:
        return None
    flt = "".join(f"[0:a]atrim={a:.2f}:{b:.2f},asetpts=PTS-STARTPTS[s{i}];" for i, (a, b) in enumerate(segs))
    flt += "".join(f"[s{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vocals), "-filter_complex", flt, "-ac", "1",
                    "-ar", "16000", "-c:a", "libopus", "-b:a", "24k", str(out)], check=True)
    return out


def verify_speakers(units: list[dict], vocals: Path | None, run_dir: Path) -> dict[str, float] | None:
    """Cosine similarity of each speaker to the consent recording; None when it cannot be checked."""
    from . import verify
    ref = verify.reference()
    if not ref or not vocals or not vocals.exists():
        return None
    scores = {}
    for s in talk_time(units):
        p = verify.speaker_sample(vocals, units, s, run_dir / f"verify_{s}.wav")
        if p:
            scores[s] = verify.cosine(ref, verify.embed(p))
    return scores


def cast(units: list[dict], vocals: Path | None, clone: str, consent: bool, run_dir: Path) -> dict[str, dict]:
    """{spk: {"voice", "why", "seconds", "match"}}. Consent is two locks: the channel has a consent recording
    on file, and the speaker's voice verifies against it. Gemini casts presets for everyone else."""
    scores = verify_speakers(units, vocals, run_dir) if consent else None
    base = default_cast(units, clone, consent, scores=scores)
    tt = talk_time(units)
    out = {s: {"voice": v, "why": "creator's cloned voice (consent on file, voice verified)" if v == clone
               else "rotation", "seconds": round(tt[s], 1),
               **({"match": scores[s]} if scores and s in scores else {})} for s, v in base.items()}
    if not vocals or not vocals.exists():
        return out
    taken = {v for v in base.values() if v == clone}
    for s, row in out.items():
        if row["voice"] == clone:
            continue
        smp = _sample(vocals, units, s, run_dir / f"spk_{s}.ogg")
        if not smp:
            continue
        options = {k: v for k, v in PRESETS.items() if k not in taken} or PRESETS
        pick = gem.json_call(
            "Listen to this speaker. Pick the dubbing voice from this list that best matches their perceived "
            f"gender, age and energy: {options}. why: one short phrase.",
            {"type": "object", "properties": {"voice": {"type": "string", "enum": list(options)},
                                              "why": {"type": "string"}}, "required": ["voice", "why"]},
            parts=[types.Part.from_bytes(data=smp.read_bytes(), mime_type="audio/ogg")])
        row.update(voice=pick["voice"], why=pick["why"])
        taken.add(pick["voice"])
    return out
