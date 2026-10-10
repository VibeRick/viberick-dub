"""Tempo decisions for one dubbed line (ratio = spoken seconds / slot seconds)."""
import subprocess
from pathlib import Path

from . import voice

MAX_TEMPO = 1.25     # above this, ask for a shorter line first
HARD_MAX = 1.35      # never speed up more than this
MIN_TEMPO = 0.92     # slow very short lines slightly, never more


def needs_shorter(dur: float, slot: float) -> bool:
    return dur / slot > MAX_TEMPO


def decide_tempo(dur: float, slot: float) -> float:
    r = dur / slot
    if r > 1.0:
        return min(r, HARD_MAX)
    return max(MIN_TEMPO, min(1.0, r / 0.8))


def stretch(src: Path, dst: Path, tempo: float) -> float:
    if abs(tempo - 1.0) < 0.01:
        dst.write_bytes(src.read_bytes())
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                        f"atempo={tempo:.4f}", "-c:a", "pcm_s16le", str(dst)], check=True)
    return voice.duration(dst)
