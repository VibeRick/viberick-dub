"""<run>/review.html: the web app's studio view (video + synced transcript + agent log), fed from local
files instead of Firestore. Open it directly from Finder."""
import base64
import json
from pathlib import Path

from . import config

WEB = config.ROOT / "web"


def job_data(run_dir: Path, units: list[dict], langs: list[str]) -> dict:
    report = json.loads((run_dir / "out" / "report.json").read_text())
    info = json.loads((run_dir / "info.json").read_text())
    outputs = {p.name: f"out/{p.name}" for p in (run_dir / "out").iterdir()}
    lines = {}
    for lang in langs:
        data = json.loads((run_dir / "dub" / f"{lang}.json").read_text())
        lines[lang] = {"report": data["report"], "rows": [
            {**r, "start": u["start"], "end": u["end"], "src": u["text"], "spk": u.get("spk"), "voice": u.get("voice")}
            for u, r in zip(units, data["rows"])]}
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]
    return {"job": {"id": run_dir.name, "title": info.get("title"), "url": f"https://youtu.be/{info.get('id')}",
                    "status": "done", "stage": "Done", "report": report, "outputs": outputs,
                    "thumbnail": f"https://i.ytimg.com/vi/{info.get('id')}/hqdefault.jpg"},
            "events": events, "lines": lines}


def write(run_dir: Path, wav: Path, units: list[dict], langs: list[str]) -> Path | None:
    if not (WEB / "index.html").exists():   # the Cloud Run worker ships without the web app
        return None
    page = (WEB / "index.html").read_text()
    css = (WEB / "style.css").read_text()
    js = (WEB / "app.js").read_text()
    logo = "data:image/png;base64," + base64.b64encode((WEB / "logo.png").read_bytes()).decode()
    data = json.dumps(job_data(run_dir, units, langs), ensure_ascii=False).replace("</", "<\\/")
    page = page.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}</style>")
    page = page.replace('src="logo.png"', f'src="{logo}"').replace('href="favicon.png"', f'href="{logo}"')
    page = page.replace('<script type="module" src="app.js"></script>',
                        f"<script>window.LOCAL_JOB = {data};</script>\n<script type=\"module\">{js}</script>")
    p = run_dir / "review.html"
    p.write_text(page)
    return p
