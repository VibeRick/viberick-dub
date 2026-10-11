"""Prepare a reviewable source ZIP without private runs, media or Git history.

This only writes local artifacts. It does not publish a repository.
"""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runs" / "source-release"
ROOT_FILES = ("README.md", "pyproject.toml", "uv.lock", "Dockerfile", ".dockerignore", ".gcloudignore", "firebase.json", "firestore.rules", ".gitignore")
WEB_FILES = ("index.html", "app.js", "style.css", "logo.png", "favicon.png")


def build() -> Path:
    files = [ROOT / name for name in ROOT_FILES]
    files += [ROOT / "web" / name for name in WEB_FILES]
    for directory in ("dub", "server", "tests", "tools"):
        files += sorted((ROOT / directory).glob("*.py"))
    files = sorted(set(files))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    archive = OUTPUT / "viberick-dub-source-review.zip"
    manifest = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for path in files:
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"Expected regular source file: {path.relative_to(ROOT)}")
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = zipfile.ZipInfo("viberick-dub/" + relative, (2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, data)
            manifest.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "status": "local review only; not published",
        "archive": archive.name,
        "exclusions": ["credentials", "local runs", "voice recordings", "video/audio media", "private ownership state", "Git history", "internal operational documents", "presentation and video production assets"],
        "files": manifest,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }, indent=2) + "\n")
    return archive


if __name__ == "__main__":
    print(build())
