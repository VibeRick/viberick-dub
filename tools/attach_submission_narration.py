"""Attach reviewed local narration to the film, using measured durations.

No generation, credentials, cloud access or publication. The manifest maps each
script section to {"text": exact_script_text, "file": path_relative_to_public}.
All files must already be in Remotion's public directory. Writes only after every
section validates and the complete film is strictly below three minutes.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

PROOF_FRAMES = 157 + 156 + 156 + 140 + 138
FPS = 30


def probe_seconds(path: Path) -> float:
    value = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)
    ], text=True)
    seconds = float(value.strip())
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Narration duration must be positive and finite")
    return seconds


def attach(script_path: Path, manifest_path: Path, public_root: Path) -> dict:
    script = json.loads(script_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    public_root = public_root.resolve()
    if set(manifest) != set(script):
        raise ValueError("Narration must cover each script section exactly once")
    for name, row in script.items():
        take = manifest[name]
        if take.get("text") != row["text"]:
            raise ValueError(f"Narration text does not match current script: {name}")
        relative = Path(take["file"])
        path = public_root / relative
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink() or not path.resolve().is_relative_to(public_root):
            raise ValueError(f"Narration must be inside the public directory: {name}")
        if path.suffix.lower() not in {".wav", ".m4a", ".mp3"} or not path.is_file():
            raise ValueError(f"Missing local audio file: {name}")
        seconds = probe_seconds(path)
        row.update(audio=relative.as_posix(), audioSeconds=seconds,
                   frames=math.ceil((seconds + .4) * FPS),
                   audioSha256=hashlib.sha256(path.read_bytes()).hexdigest())
    total = PROOF_FRAMES + sum(row["frames"] for row in script.values())
    if total >= 180 * FPS:
        raise ValueError(f"Film is {total/FPS:.2f}s; shorten narration before attaching")
    temporary = script_path.with_suffix(".json.pending")
    temporary.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(script_path)
    return {"frames": total, "seconds": total / FPS, "sections": len(script)}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "demo" / "remotion"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--script", type=Path, default=root / "src/submission-script.json")
    parser.add_argument("--public-root", type=Path, default=root / "public")
    args = parser.parse_args()
    print(json.dumps(attach(args.script, args.manifest, args.public_root)))
