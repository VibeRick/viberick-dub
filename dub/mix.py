"""Lay dubbed clips on the original timeline, then mix with the background bed."""
import subprocess
import wave
from pathlib import Path

from . import voice


GAP = 0.08        # minimum silence between two separately anchored lines
MAX_EARLY = 2.0   # a flowing line may start at most this much before its source line


def place(units: list[dict], clips: list[Path], total: float, out: Path,
          flow: list[float | None] | None = None) -> dict:
    """flow[i] = None: anchor line i to its source start. A number: line i continues the previous one;
    place it that many seconds after the previous clip ends, but never more than MAX_EARLY early."""
    rate = voice.RATE
    buf = bytearray((int(total * rate) + rate) * 2)
    cursor, late, starts = None, [], []
    flow = flow or [None] * len(units)
    for i, (u, c) in enumerate(zip(units, clips)):
        if cursor is None:
            start = u["start"]
        elif flow[i] is not None:
            start = max(cursor + flow[i], u["start"] - MAX_EARLY)
        else:
            start = max(u["start"], cursor + GAP)
        starts.append(round(start, 3))
        late.append(max(0.0, start - u["start"]))
        pcm = voice.pcm(c)
        a = int(start * rate) * 2
        b = min(len(buf), a + len(pcm))
        if a < len(buf):
            buf[a:b] = pcm[: b - a]
        cursor = start + len(pcm) / 2 / rate
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(bytes(buf))
    s = sorted(late) or [0.0]
    return {"late_max": round(s[-1], 2), "late_p95": round(s[int(len(s) * 0.95)], 2),
            "late_lines": sum(1 for x in late if x > 0.3), "starts": starts}


def mix(voice_wav: Path, bed: Path | None, out: Path) -> None:
    if bed:
        fc = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];[1:a]aresample=48000[b];"
              "[v][b]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11")
        cmd = ["-i", str(voice_wav), "-i", str(bed), "-filter_complex", fc]
    else:
        cmd = ["-i", str(voice_wav), "-af", "aresample=48000,pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1.5:LRA=11"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd, "-ar", "48000", "-c:a", "aac", "-b:a", "160k",
                    str(out)], check=True)
