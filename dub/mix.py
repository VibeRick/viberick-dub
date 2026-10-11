"""Lay dubbed clips on the original timeline, then mix with the background bed."""
import array
import math
import subprocess
import wave
from pathlib import Path

from . import voice


GAP = 0.08
MAX_EARLY = 0.35  # local breathing adjustment, never a multi-second dialogue shift


def place(units: list[dict], clips: list[Path], total: float, out: Path,
          flow: list[float | None] | None = None) -> dict:
    """Place complete clips; respect anchors unless same-speaker content would overlap.

    Overlapping turns mix additively instead of pushing the next speaker late. Same-speaker
    overflow remains visible in metrics; no content is silently cut to satisfy an anchor.
    """
    rate = voice.RATE
    buf = array.array("i", [0]) * int(total * rate)
    cursor, starts, ends, offsets = None, [], [], []
    overlaps = 0
    speaker_ends = {}
    anchor_violations = 0
    flow = flow or [None] * len(units)
    for i, (u, c) in enumerate(zip(units, clips)):
        hard = i > 0 and (u.get("spk") != units[i - 1].get("spk")
                            or u.get("hard_anchor") or u.get("scene_cut"))
        if cursor is None or hard:
            start = u["start"]
        elif flow[i] is not None:
            start = max(cursor + flow[i], u["start"] - MAX_EARLY)
        else:
            start = max(u["start"], cursor + GAP)
        own_end = speaker_ends.get(u.get("spk") or "default")
        if own_end is not None:
            start = max(start, own_end + (0.0 if flow[i] == 0 and not hard else GAP))
        start = max(0.0, start)
        if (u.get("hard_anchor") or u.get("scene_cut")) and start > u["start"] + .001:
            anchor_violations += 1
        pcm = array.array("h", voice.pcm(c))
        end = start + len(pcm) / rate
        if cursor is not None and start < cursor:
            overlaps += 1
        starts.append(round(start, 3)); ends.append(round(end, 3))
        offsets.append(start - u["start"])
        a = int(start * rate)
        if a + len(pcm) > len(buf):
            buf.extend([0] * (a + len(pcm) - len(buf)))
        if cursor is None or start >= cursor:
            buf[a:a + len(pcm)] = array.array("i", pcm)
        else:
            for k, sample in enumerate(pcm):
                buf[a + k] += sample
        cursor = max(cursor or 0.0, end)
        speaker_ends[u.get("spk") or "default"] = end
    peak = max((abs(x) for x in buf), default=0)
    gain = min(1.0, 32767 / peak) if peak else 1.0
    pcm_out = array.array("h", (int(x * gain) for x in buf))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm_out.tobytes())
    stats = {"starts": starts, "ends": ends, "overlap_lines": overlaps, "anchor_violation_lines": anchor_violations,
             "overlap_headroom_gain_db": round(20 * math.log10(gain), 3),
             "tail_overflow": round(max(0.0, max(ends, default=0.0) - total), 3)}
    for name, values in (("late", [max(0., x) for x in offsets]),
                         ("early", [max(0., -x) for x in offsets]),
                         ("absolute", [abs(x) for x in offsets])):
        ordered = sorted(values) or [0.0]
        stats.update({f"{name}_max": round(ordered[-1], 3),
                      f"{name}_p95": round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 3),
                      f"{name}_lines": sum(x > .3 for x in values)})
    return stats


def mix(voice_wav: Path, bed: Path | None, out: Path) -> None:
    if bed:
        fc = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];[1:a]aresample=48000[b];"
              "[v][b]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11")
        cmd = ["-i", str(voice_wav), "-i", str(bed), "-filter_complex", fc]
    else:
        cmd = ["-i", str(voice_wav), "-af", "aresample=48000,pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1.5:LRA=11"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd, "-ar", "48000", "-c:a", "aac", "-b:a", "160k",
                    str(out)], check=True)
