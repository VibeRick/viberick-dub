"""Publish a finished local run as a job in Firestore + public GCS (e.g. the showcase examples).

uv run python -m tools.publish_run runs/Fty2sz3dBwU.180s [--demo]"""
import argparse
import json
import time
from pathlib import Path

from dub import cloud

ap = argparse.ArgumentParser()
ap.add_argument("run_dir")
ap.add_argument("--demo", action="store_true")
a = ap.parse_args()
run_dir = Path(a.run_dir)
info = json.loads((run_dir / "info.json").read_text())
report = json.loads((run_dir / "out" / "report.json").read_text())
job_id = f"{info['id']}-{run_dir.name.split('.')[-1] if '.' in run_dir.name else 'full'}"
ref = cloud.job(job_id)
ref.set({"url": f"https://youtu.be/{info['id']}", "video": info["id"], "title": info["title"],
         "thumbnail": f"https://i.ytimg.com/vi/{info['id']}/hqdefault.jpg", "langs": [l["lang"] for l in report["langs"]],
         "max_sec": report["duration"], "status": "running", "stage": "Publishing", "created": time.time(),
         "demo": a.demo})
for old in ref.collection("events").stream():
    old.reference.delete()
batch, n = cloud.db().batch(), 0
for line in (run_dir / "events.jsonl").read_text().splitlines():
    batch.set(ref.collection("events").document(), json.loads(line))
    n += 1
    if n % 400 == 0:
        batch.commit()
        batch = cloud.db().batch()
batch.commit()
cloud.publish_results(run_dir, job_id, [l["lang"] for l in report["langs"]])
urls = cloud.upload_outputs(run_dir, job_id)
ref.update({"status": "done", "stage": "Done", "outputs": urls, "report": report, "finished": time.time()})
print(job_id, n, "events")
