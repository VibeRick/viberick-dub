"""Voice / background split with demucs htdemucs on CPU. Output: vocals.wav, bed.wav (48 kHz)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def separate(run_dir: Path, source: Path | None = None) -> tuple[Path, Path]:
    vocals, bed = run_dir / "vocals.wav", run_dir / "bed.wav"
    if vocals.exists() and bed.exists():
        return vocals, bed
    src = source or run_dir / "source.wav"
    out = run_dir / "sep"
    # In the container demucs is installed in the main env; locally it lives in the `sep` group.
    py = [sys.executable] if os.environ.get("DUB_IN_CONTAINER") else ["uv", "run", "--group", "sep", "python"]
    subprocess.run([*py, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs", "-d", "cpu",
                    "-o", str(out), str(src)], check=True)
    d = out / "htdemucs" / src.stem
    shutil.move(d / "vocals.wav", vocals)
    shutil.move(d / "no_vocals.wav", bed)
    shutil.rmtree(out)
    return vocals, bed
