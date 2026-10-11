"""Offline, reproducible energy/timing audit; never a language or intelligibility score.

Audio is decoded to 16 kHz mono PCM. A 20 ms frame is active when its RMS is
above a configurable dBFS threshold (default -40). No ML VAD, hangover, or noise
estimation is applied. Music/noise can count as speech; separated vocals are
preferred. All source-overlap comparisons use the SAME source-duration window,
so moving speech beyond the end cannot improve the measured coverage.
"""
import array
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .translate import script_issue

RATE = 16000
FRAME_SECONDS = 0.02


@dataclass
class Activity:
    mask: list[bool]
    duration: float
    frame_seconds: float = FRAME_SECONDS


def audio_activity(path: Path, threshold_dbfs: float = -40.0) -> Activity:
    if not math.isfinite(threshold_dbfs) or not -100 <= threshold_dbfs <= 0:
        raise ValueError("threshold_dbfs must be between -100 and 0")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                          "-ar", str(RATE), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    pcm = array.array("h", raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    frame = round(RATE * FRAME_SECONDS)
    energy = (32768 * 10 ** (threshold_dbfs / 20)) ** 2
    mask = []
    for start in range(0, len(pcm), frame):
        samples = pcm[start:start + frame]
        mask.append(sum(x * x for x in samples) / len(samples) > energy)
    return Activity(mask, len(pcm) / RATE)


def _intervals(mask: list[bool], frame: float, end: float) -> list[tuple[float, float]]:
    intervals, start = [], None
    for i, active in enumerate([*mask, False]):
        if active and start is None:
            start = i * frame
        elif not active and start is not None:
            intervals.append((start, min(i * frame, end)))
            start = None
    return intervals


def _seconds(mask: list[bool], frame: float, end: float) -> float:
    return sum(b - a for a, b in _intervals(mask, frame, end))


def _round(value: float) -> float:
    return round(value, 3)


def compare_activity(source: Activity, dubbed: Activity, source_duration: float) -> dict:
    """Fixed source window, with missing dub/source frames explicitly treated as silent."""
    if not math.isfinite(source_duration) or source_duration <= 0:
        raise ValueError("source_duration must be positive and finite")
    if source.frame_seconds != dubbed.frame_seconds:
        raise ValueError("Activity frame sizes must match")
    frame = source.frame_seconds
    n = math.ceil(source_duration / frame)
    src = [source.mask[i] if i < len(source.mask) else False for i in range(n)]
    dub = [dubbed.mask[i] if i < len(dubbed.mask) else False for i in range(n)]
    missing = [s and not d for s, d in zip(src, dub)]
    gaps = []
    for a, b in _intervals([not d for d in dub], frame, source_duration):
        overlap = sum(min((i + 1) * frame, b) - max(i * frame, a)
                      for i in range(int(round(a / frame)), min(n, math.ceil(b / frame))) if src[i])
        if overlap > 0:
            gaps.append({"start": _round(a), "end": _round(b), "seconds": _round(b - a),
                         "source_active_seconds": _round(overlap)})
    source_active = _seconds(src, frame, source_duration)
    dub_active = _seconds(dub, frame, source_duration)
    beyond = sum(max(0, b - max(a, source_duration))
                 for a, b in _intervals(dubbed.mask, frame, dubbed.duration))
    return {
        "comparison_window_seconds": source_duration,
        "source_detected_active_seconds": _round(source_active),
        "source_detected_silence_seconds": _round(source_duration - source_active),
        "dub_detected_active_seconds": _round(dub_active),
        "dub_detected_silence_seconds": _round(source_duration - dub_active),
        "excess_silence_seconds": _round(max(0, source_active - dub_active)),
        "source_active_dub_silent_seconds": _round(_seconds(missing, frame, source_duration)),
        "source_active_coverage_fraction": _round(1 - _seconds(missing, frame, source_duration) / source_active)
        if source_active else None,
        "dub_file_detected_silence_seconds": _round(dubbed.duration - _seconds(dubbed.mask, frame, dubbed.duration)),
        "dub_active_beyond_source_seconds": _round(beyond),
        "source_audio_missing_seconds": _round(max(0, source_duration - source.duration)),
        "dub_audio_missing_seconds": _round(max(0, source_duration - dubbed.duration)),
        "gaps_over_0_5_seconds_during_source_activity": sum(g["seconds"] > .5 for g in gaps),
        "gaps_over_1_second_during_source_activity": sum(g["seconds"] > 1 for g in gaps),
        "gaps": gaps,
    }


def audit_lines(rows: list[dict], units: list[dict], timeline: list[dict], lang: str,
                dubbed_duration: float, source_duration: float) -> dict:
    source = {u["id"]: u for u in units}
    placed = {r["id"]: r for r in timeline}
    offsets, ends, flagged, missing = [], [], [], []
    for row in rows:
        ident = row["id"]
        unit = source.get(ident, {})
        position = placed.get(ident, row)
        start = position.get("dub_start", position.get("start"))
        end = position.get("dub_end", position.get("end"))
        source_start = position.get("source_start", unit.get("start"))
        issues = []
        for field in ("text", "heard"):
            issue = script_issue(row.get(field, ""), lang)
            if issue:
                issues.append(f"{field}: {issue}")
        if row.get("ok") is False:
            issues.append(row.get("issue") or "Automated line check failed")
        if start is None or end is None or source_start is None:
            missing.append(ident)
        else:
            offset = start - source_start
            offsets.append(offset)
            ends.append(end)
            if abs(offset) > .3:
                issues.append(f"Placement offset {offset:+.3f}s")
            if end > dubbed_duration + .02:
                issues.append("Placed line extends beyond audio file")
            if end > source_duration + .02:
                issues.append("Placed line extends beyond source video duration")
        if issues:
            flagged.append({"id": ident, "issues": issues})
    timing = {}
    for name, values in (("early", [max(0, -x) for x in offsets]), ("late", [max(0, x) for x in offsets]),
                         ("absolute", [abs(x) for x in offsets])):
        ordered = sorted(values)
        timing[name] = {"max_seconds": _round(max(ordered)),
                        "p95_seconds": _round(ordered[max(0, math.ceil(.95 * len(ordered)) - 1)]),
                        "lines_over_0_3_seconds": sum(x > .3 for x in values)} if ordered else None
    expected_end = max(ends) if ends else None
    return {"timing": timing, "timing_available_lines": len(offsets), "timing_missing_line_ids": missing,
            "tail": {"placed_end_seconds": expected_end,
                     "missing_audio_seconds": _round(max(0, expected_end - dubbed_duration)) if ends else None,
                     "overflow_past_source_seconds": _round(max(0, expected_end - source_duration)) if ends else None,
                     "placed_audio_complete": not missing and set(source) <= {r["id"] for r in rows}
                     and expected_end is not None and expected_end <= dubbed_duration + .02},
            "flagged_lines": flagged,
            "unrepresented_source_line_ids": sorted(set(source) - {r["id"] for r in rows})}


def _fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return {"path": str(path.resolve()), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def audit_run(run_dir: Path, threshold_dbfs: float = -40.0) -> dict:
    summary_path = run_dir / "out" / "report.json"
    summary = json.loads(summary_path.read_text())
    units_path = run_dir / "units.json"
    units = json.loads(units_path.read_text())
    source = run_dir / "vocals.wav"
    separated = source.is_file()
    if not separated:
        source = run_dir / "source.wav"
    source_activity = audio_activity(source, threshold_dbfs)
    duration = summary["duration"]
    languages = {}
    for entry in summary["langs"]:
        lang = entry["lang"]
        voice_path = run_dir / "dub" / f"{lang}.voice.wav"
        rows_path = run_dir / "dub" / f"{lang}.json"
        timeline_path = run_dir / "out" / f"timeline.{lang}.json"
        rows = json.loads(rows_path.read_text())["rows"]
        timeline = json.loads(timeline_path.read_text()) if timeline_path.exists() else []
        dubbed = audio_activity(voice_path, threshold_dbfs)
        languages[lang] = {"audio": compare_activity(source_activity, dubbed, duration),
                           "lines": audit_lines(rows, units, timeline, lang, dubbed.duration, duration),
                           "inputs": [_fingerprint(p) for p in [voice_path, rows_path, *([timeline_path] if timeline else [])]]}
    return {"schema_version": 1, "run": str(run_dir.resolve()),
            "method": {"kind": "RMS energy heuristic, not speech recognition or intelligibility evaluation",
                       "sample_rate": RATE, "frame_seconds": FRAME_SECONDS, "threshold_dbfs": threshold_dbfs,
                       "source_separated_vocals": separated,
                       "caveats": ["Music/noise may be counted as speech, especially without separated vocals.",
                                   "Timing is unavailable for legacy rows without recorded placements.",
                                   "Script leakage checks inspect cached text/heard transcripts, not audio language.",
                                   "Tail completeness means recorded placement fits the WAV; it does not prove meaning or listening quality.",
                                   "Gap counts use dub-silent intervals exceeding the threshold with any source-active overlap."]},
            "inputs": [_fingerprint(p) for p in (source, summary_path, units_path)], "languages": languages}
