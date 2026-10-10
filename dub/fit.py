"""Tempo decisions for one dubbed line (ratio = spoken seconds / slot seconds)."""
import subprocess
from pathlib import Path

from . import voice

MAX_TEMPO = 1.25     # above this, ask for a shorter line first
HARD_MAX = 1.35      # never speed up more than this
MIN_TEMPO = 0.92     # slow very short lines slightly, never more


def needs_shorter(dur: float, slot: float) -> bool:
    return dur / slot > MAX_TEMPO


def decide_tempo(dur: float, slot: float, allow_slow: bool = True) -> float:
    """allow_slow=False for lines cut from a paragraph take: they flow back to back, so slowing
    a short line would only add drag."""
    r = dur / slot
    if r > 1.0:
        return min(r, HARD_MAX)
    if not allow_slow:
        return 1.0
    return max(MIN_TEMPO, min(1.0, r / 0.8))


# Short fades at both ends: a clip that starts or stops mid-waveform clicks when laid on the timeline.
EDGES = "afade=t=in:d=0.008,areverse,afade=t=in:d=0.015,areverse"


def stretch(src: Path, dst: Path, tempo: float) -> float:
    flt = EDGES if abs(tempo - 1.0) < 0.01 else f"atempo={tempo:.4f},{EDGES}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", flt, "-c:a", "pcm_s16le",
                    str(dst)], check=True)
    return voice.duration(dst)
