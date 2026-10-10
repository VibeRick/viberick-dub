"""YouTube URL → source.mp4, source.wav (48 kHz stereo), source.stt.flac (16 kHz mono), info.json."""
import json
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


def fetch(url: str, run_dir: Path) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    info_p = run_dir / "info.json"
    if info_p.exists() and (run_dir / "source.wav").exists():
        return json.loads(info_p.read_text())
    if not (run_dir / "source.mp4").exists():
        cmd = ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
               "--merge-output-format", "mp4", "-o", str(run_dir / "source.%(ext)s"),
               "--write-info-json", "--no-playlist", url]
        if proxy := os.environ.get("DUB_PROXY"):
            cmd[1:1] = ["--proxy", proxy]
        subprocess.run(cmd, check=True)
    raw = json.loads((run_dir / "source.info.json").read_text())
    for args, name in ((["-ac", "2", "-ar", "48000"], "source.wav"),
                       (["-ac", "1", "-ar", "16000", "-c:a", "flac"], "source.stt.flac")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(run_dir / "source.mp4"), "-vn",
                        *args, str(run_dir / name)], check=True)
    info = {k: raw.get(k) for k in ("id", "title", "channel", "duration", "description", "tags")}
    info_p.write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info
