"""Synthesize ≤5 consecutive lines in one take, then cut it back into lines.

Cut points: Chirp 3 sync recognition on the take → word times → align each line's characters →
cut midway between the previous line's last word and this line's first word."""
import subprocess
from pathlib import Path

from . import align, stt, voice


def groups(units: list[dict], max_lines: int = 5, max_gap: float = 1.5, max_sec: float = 32.0) -> list[list[int]]:
    out, cur = [], []
    for i, u in enumerate(units):
        if cur:
            gap = u["start"] - units[cur[-1]]["end"]
            span = u["end"] - units[cur[0]]["start"]
            if gap > max_gap or len(cur) >= max_lines or span > max_sec:
                out.append(cur)
                cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def cut_points(lines: list[str], words: list[dict]) -> list[float] | None:
    cues = align.retime(lines, words)
    if len(cues) != len(lines):
        return None
    pts = [0.0]
    for prev, cur in zip(cues, cues[1:]):
        if cur["start"] < prev["end"]:
            return None
        pts.append(round((prev["end"] + cur["start"]) / 2, 3))
    return pts


def synth_group(lines: list[str], lang: str, d: Path, ids: list[int]) -> bool:
    take = d / f"take_{ids[0]:04d}.wav"
    voice.synth(" ".join(lines), take)
    if len(lines) == 1:
        take.replace(d / f"{ids[0]:04d}.tts.wav")
        return True
    pts = cut_points(lines, stt.chirp_sync_words(take.read_bytes(), lang))
    end = voice.duration(take)
    if pts is None or pts[-1] >= end - 0.05:
        take.unlink()
        return False
    for k, i in enumerate(ids):
        a, b = pts[k], (pts[k + 1] if k + 1 < len(pts) else end)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(take), "-ss", f"{a:.3f}", "-to",
                        f"{b:.3f}", "-af", "afade=t=in:d=0.012", "-c:a", "pcm_s16le",
                        str(d / f"{i:04d}.tts.wav")], check=True)
    take.unlink()
    return True
