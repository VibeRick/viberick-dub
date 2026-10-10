"""<run>/review.html: listen to the original and each dub; inspect every line the agent touched."""
import html
import json
from pathlib import Path


def write(run_dir: Path, wav: Path, units: list[dict], langs: list[str]) -> Path:
    parts = [f"<h1>{html.escape(run_dir.name)}</h1><p>Original</p><audio controls src='{wav.name}'></audio>"]
    for lang in langs:
        data = json.loads((run_dir / "dub" / f"{lang}.json").read_text())
        rep = data["report"]
        video = f"out/video.{lang}.mp4"
        player = (f"<video controls width=640 src='{video}'></video>" if (run_dir / video).exists()
                  else f"<audio controls src='out/dub.{lang}.m4a'></audio>")
        parts.append(f"<h2>{lang}: {rep['ok']}/{rep['lines']} ok · late p95 {rep['late_p95']}s</h2>{player}"
                     "<table border=1 cellpadding=4 style='border-collapse:collapse'>"
                     "<tr><th>#</th><th>t</th><th>source</th><th>dub</th><th>tempo</th><th>ok</th><th>actions</th></tr>")
        for u, r in zip(units, data["rows"]):
            acts = " → ".join(a["do"] for a in r["actions"])
            parts.append(f"<tr><td>{u['id']}</td><td>{u['start']:.1f}</td><td>{html.escape(u['text'])}</td>"
                         f"<td>{html.escape(r['text'])}</td><td>{r['tempo']}</td>"
                         f"<td>{'✓' if r['ok'] else '✗ ' + html.escape(r['issue'])}</td><td>{acts}</td></tr>")
        parts.append("</table>")
    p = run_dir / "review.html"
    p.write_text("<meta charset=utf-8><body style='font:14px system-ui;max-width:1100px;margin:auto'>" + "".join(parts))
    return p
