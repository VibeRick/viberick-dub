"""Assemble a completed, budgeted full validation with an existing clean source, without API calls."""
import argparse
import json
from pathlib import Path
import shutil

from dub import pipeline


def assemble(baseline: Path, validation: Path, clean_source: Path, output: Path) -> Path:
    if output.exists():
        raise ValueError("Choose a new output directory; accepted and baseline runs are never replaced")
    units = json.loads((baseline / "units.json").read_text())
    rows = json.loads((validation / "results.json").read_text())
    plan = json.loads((validation / "plan.json").read_text())
    if set(rows) != set(plan["languages"]):
        raise ValueError("Not all requested languages completed")
    ids = [u["id"] for u in units]
    if any([r["id"] for r in values] != ids for values in rows.values()):
        raise ValueError("Only full validation sets can be assembled; stress-set clips remain separate")
    if not (validation / "budget.json").exists():
        raise ValueError("Validation is still running or has no final budget evidence")
    for lang, values in rows.items():
        for row in values:
            if not (validation / "dub" / lang / f"{row['id']:04d}.wav").exists():
                raise ValueError("A validated audio clip is missing")
    shutil.copytree(baseline, output)
    shutil.copy2(clean_source, output / "source.mp4")
    shutil.copy2(clean_source, output / "clean-source.mp4")
    # Old public derivatives must not survive under an unchanged filename.
    shutil.rmtree(output / "out")
    (output / "out").mkdir()
    summary = json.loads((baseline / "out/report.json").read_text())
    start = (validation / "plan.json").stat().st_mtime
    end = (validation / "budget.json").stat().st_mtime
    summary.update(langs=[], sec_total=round(max(0, end - start), 1),
                   timing_provenance="Local validation artifact timestamps; not Cloud Run latency",
                   validation=str(validation.resolve()), generation_updated=True,
                   gemini_text_usd=None, tts_calls=None)
    for lang, values in rows.items():
        shutil.rmtree(output / "dub" / lang)
        shutil.copytree(validation / "dub" / lang, output / "dub" / lang)
        report = {"lang": lang, "lines": len(values), "ok": sum(r["ok"] is True for r in values), "sec": None,
                  "timing_provenance": "Per-language wall time not separately recorded"}
        (output / "dub" / f"{lang}.json").write_text(json.dumps({"rows": values, "report": report}, ensure_ascii=False))
        summary["langs"].append(report)
    (output / "out/report.json").write_text(json.dumps(summary, ensure_ascii=False))
    shutil.copy2(validation / "events.jsonl", output / "events.jsonl")
    for name in ("plan.json", "budget.json"):
        shutil.copy2(validation / name, output / ("validation-" + name))
    # Cut recognition must refer to the caption-free source rather than a previous cache.
    (output / "scene-cuts.json").unlink(missing_ok=True)
    pipeline.offline_remix(output)
    pipeline._ff("-i", str(clean_source), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "aac",
                 "-b:a", "160k", "-movflags", "+faststart", str(output / "out/video.orig.mp4"))
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline", type=Path)
    p.add_argument("validation", type=Path)
    p.add_argument("clean_source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(assemble(a.baseline, a.validation, a.clean_source, a.output))
