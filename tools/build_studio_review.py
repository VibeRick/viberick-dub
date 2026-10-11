"""Build an explicit local recorded-run fixture; does not upload or generate speech."""
import argparse
import json
from pathlib import Path
import shutil

from dub.cloud import result_document


def build(run: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / ".gitignore").write_text("*\n!.gitignore\n")
    report = json.loads((run / "out/report.json").read_text())
    info_path = run / "info.json"
    info = json.loads(info_path.read_text()) if info_path.exists() else {}
    speakers = report.get("speakers") or info.get("speakers") or {}
    if speakers:
        report = {**report, "speakers": speakers}
    source_captioned = info.get("source_captioned", report.get("source_captioned"))
    if (run / "clean-source.mp4").exists():
        source_captioned = False
    if not isinstance(source_captioned, bool):
        source_captioned = None
    title = info.get("title") or report.get("title") or run.name
    alignment_path = run / "source-alignment.json"
    alignment = json.loads(alignment_path.read_text()) if alignment_path.exists() else {}
    source_url = info.get("source_url") or "https://youtu.be/" + report["video"]
    langs = [r["lang"] for r in report["langs"]]
    outputs = {}
    for lang in ["orig", *langs]:
        media = run / "out" / f"video.clean.{lang}.mp4"
        if not media.exists():
            media = run / "out" / f"video.{lang}.mp4"
        shutil.copy2(media, destination / media.name)
        outputs[f"video.{lang}.mp4"] = media.name
    for media in (run / "out").iterdir():
        if media.is_file() and media.suffix in (".m4a", ".srt", ".vtt", ".json", ".wav"):
            shutil.copy2(media, destination / media.name)
            outputs[media.name] = media.name
    data = {"job": {"id": run.name, "title": title,
                    "status": "done", "src": report["src"], "url": source_url,
                    "source_interval": info.get("source_interval"),
                    "voice_disclosure": info.get("voice_disclosure") or report.get("voice_disclosure"),
                    "alignment_provenance": alignment.get("method"),
                    "validation_scope": "prepared_source_turns" if alignment else None,
                    "langs": langs, "outputs": outputs, "report": report,
                    "can_regenerate": False, "source_captioned": source_captioned, "speakers": speakers},
            "lines": {lang: result_document(run, lang) for lang in langs},
            "events": [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]}
    manifest = destination / "manifest.json"
    manifest.write_text(json.dumps(data, ensure_ascii=False))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("web/review"))
    args = parser.parse_args()
    print(build(args.run, args.destination))
