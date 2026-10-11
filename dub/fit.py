"""Fitting one dubbed line to its slot (ratio = spoken seconds / slot seconds).

Speech is never sped up or slowed down (2026-10-11, by ear on a 20-minute lecture: atempo on 100 of 364
lines was heard as rushed). A line that runs long is re-translated shorter instead; what still runs over
spills into the next pause and is caught up there (mix.place)."""
import os
import subprocess
from pathlib import Path

from . import voice

MAX_OVERRUN = float(os.environ.get("DUB_MAX_OVERRUN", "1.25"))   # above this, ask for a shorter line


def needs_shorter(dur: float, slot: float) -> bool:
    return dur / slot > MAX_OVERRUN


# Short fades at both ends: a clip that starts or stops mid-waveform clicks when laid on the timeline.
EDGES = "afade=t=in:d=0.008,areverse,afade=t=in:d=0.015,areverse"


def finish(src: Path, dst: Path) -> float:
    """The clip as spoken, only its edges faded."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", EDGES, "-c:a", "pcm_s16le",
                    str(dst)], check=True)
    return voice.duration(dst)
