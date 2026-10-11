"""YouTube URL → source.mp4, source.wav (48 kHz stereo), source.stt.flac (16 kHz mono), info.json.

YouTube asks cloud IPs to sign in, so on failure the download is retried through DUB_PROXY (a residential
proxy). With max_sec only that section is downloaded, at ≤720p, to keep proxy bandwidth small."""
import json
import math
import os
import re
import subprocess
from pathlib import Path

_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str:
    if m := _ID.search(url):
        return m.group(1)
    out = subprocess.run(["yt-dlp", "--get-id", url], capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1]


def _cmd(url: str, out_tmpl: str, max_sec: float | None, proxy: str | None) -> list[str]:
    h = 720 if max_sec else 1080
    cmd = ["yt-dlp", "-f", f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[ext=mp4][height<={h}]/bv*[height<={h}]+ba/b",
           "--merge-output-format", "mp4", "-o", out_tmpl, "--write-info-json", "--no-playlist",
           "--force-overwrites", url]
    if max_sec:
        cmd[1:1] = ["--download-sections", f"*0-{int(max_sec) + 2}"]
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    return cmd


def fetch(url: str, run_dir: Path, max_sec: float | None = None) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    info_p = run_dir / "info.json"
    if info_p.exists() and (run_dir / "source.wav").exists():
        info = json.loads(info_p.read_text())
        if not info.get("partial_sec") or (max_sec and info["partial_sec"] >= max_sec):
            return info
    tmpl = str(run_dir / "source.%(ext)s")
    r = subprocess.run(_cmd(url, tmpl, max_sec, None), capture_output=True, text=True)
    if r.returncode != 0 and (proxy := os.environ.get("DUB_PROXY")):
        r = subprocess.run(_cmd(url, tmpl, max_sec, proxy), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not download the video. Check that it is public and available, then retry.")
    raw = json.loads((run_dir / "source.info.json").read_text())
    duration = raw.get("duration")
    if raw.get("is_live") or raw.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise ValueError("Live streams are not supported. Use a finished video with a known duration.")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("This video's duration is unavailable. Use a finished video with a known duration.")
    for args, name in ((["-ac", "2", "-ar", "48000"], "source.wav"),
                       (["-ac", "1", "-ar", "16000", "-c:a", "flac"], "source.stt.flac")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(run_dir / "source.mp4"), "-vn",
                        *args, str(run_dir / name)], check=True)
    info = {k: raw.get(k) for k in ("id", "title", "channel", "channel_id", "duration", "description", "tags",
                                    "thumbnail")}
    if max_sec and raw.get("duration", 0) > max_sec:
        info["partial_sec"] = max_sec
    info_p.write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info
