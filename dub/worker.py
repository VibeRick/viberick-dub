"""Cloud Run Job entrypoint: run one job from Firestore, mirror events live, publish outputs.

JOB_ID=<id> python -m dub.worker"""
import json
import os
import time
import traceback

from . import cloud, events, pipeline


def run(job_id: str) -> None:
    ref = cloud.job(job_id)
    spec = ref.get().to_dict()
    ref.update({"status": "running", "started": time.time()})
    events._sinks.append(cloud.event_sink(job_id))
    try:
        run_dir = pipeline.main(spec["url"], spec.get("langs") or None, spec.get("max_sec") or None)
        urls = cloud.upload_outputs(run_dir, job_id)
        report = json.loads((run_dir / "out" / "report.json").read_text())
        cloud.publish_results(run_dir, job_id, [r["lang"] for r in report["langs"]])
        ref.update({"status": "done", "stage": "Done", "outputs": urls, "report": report,
                    "finished": time.time()})
    except Exception as e:  # noqa: BLE001  surfaced to the UI, then re-raised for Cloud Run
        ref.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:500], "finished": time.time()})
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run(os.environ["JOB_ID"])
