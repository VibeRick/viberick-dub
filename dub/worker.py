"""Cloud Run worker with independent liveness, incremental results and isolated edit previews."""
import json
import os
import signal
import sys
import tempfile
import threading
import time
import traceback
import uuid
from google.cloud import firestore
from pathlib import Path

from . import cloud, events, pipeline

ERROR = "The worker could not finish this run. Finished language tracks remain available."


def on_terminate(ref):
    def handler(signum, frame):
        try:
            ref.update({"status": "error", "error": "The worker was stopped. Please try again.",
                        "finished": time.time()})
        finally:
            sys.exit(1)
    return handler


LEASE_SEC = 180


def claim(ref):
    token = uuid.uuid4().hex
    @firestore.transactional
    def acquire(tx):
        data = ref.get(transaction=tx).to_dict() or {}
        if data.get("status", "queued") != "queued":
            return None
        tx.update(ref, {"status": "running", "started": time.time(), "heartbeat": time.time(),
                        "lease_token": token, "lease_until": time.time() + LEASE_SEC})
        return token
    return acquire(cloud.db().transaction())


def fenced_update(ref, token, values):
    @firestore.transactional
    def update(tx):
        data = ref.get(transaction=tx).to_dict() or {}
        if (data.get("lease_token") != token or data.get("status") != "running"
                or data.get("lease_until", 0) < time.time()):
            return False
        tx.update(ref, values)
        return True
    return update(cloud.db().transaction())


def heartbeat(ref, stop, token=None):
    while not stop.wait(20):
        try:
            if token:
                if not fenced_update(ref, token, {"heartbeat": time.time(), "lease_until": time.time() + LEASE_SEC}):
                    return
            else:
                ref.update({"heartbeat": time.time()})
        except Exception:
            traceback.print_exc()


def preview(job_id: str, edit_id: str, lease_token=None):
    access_ref = cloud.access(job_id)
    private = access_ref.get().to_dict() or {}
    ref = cloud.job(job_id)
    edit_ref = ref.collection("edits").document(edit_id)
    edit = edit_ref.get().to_dict() or {}
    if edit.get("status") in {"ready", "accepted", "discarded", "error"}:
        return  # Cloud Run delivery retries must not overwrite a completed preview.
    if private.get("active_edit") != edit_id or edit.get("status") not in {"queued", "running"}:
        raise ValueError("Preview request is no longer active")
    lease_token = lease_token or claim(edit_ref)
    if not lease_token:
        return
    with tempfile.TemporaryDirectory(prefix="dub-edit-") as tmp:
        work = Path(tmp)
        cloud.load_workspace(private["workspace"], work)
        report = pipeline.regenerate_line(work, edit["lang"], edit["line_id"], edit["text"])
        spec = ref.get().to_dict() or {}
        if not fenced_update(edit_ref, lease_token, {"stage": "Saving preview"}):
            return
        outputs = cloud.upload_outputs(work, job_id, bool(spec.get("demo")), lang=edit["lang"], revision=edit_id)
        workspace = cloud.save_workspace(work, job_id, edit_id)
        result = cloud.result_document(work, edit["lang"])
        access_ref.collection("edits").document(edit_id).set({"workspace": workspace, "result": result})
        row = next(r for r in result["rows"] if r["id"] == edit["line_id"])
        fenced_update(edit_ref, lease_token, {"status": "ready", "outputs": outputs, "report": report, "row": row,
                         "finished": time.time()})


def run(job_id: str, edit_id: str | None = None) -> None:
    ref = cloud.job(job_id)
    progress = ref.collection("edits").document(edit_id) if edit_id else ref
    lease_token = claim(progress)
    if not lease_token:
        return
    def terminate(signum, frame):
        fenced_update(progress, lease_token, {"status": "error", "error": "The worker was stopped. Please try again.", "finished": time.time()})
        raise SystemExit(1)
    signal.signal(signal.SIGTERM, terminate)
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(progress, stop, lease_token), daemon=True)
    thread.start()
    sink = cloud.event_sink(job_id)
    events._sinks.append(sink)
    try:
        if edit_id:
            preview(job_id, edit_id, lease_token)
            return
        spec = ref.get().to_dict()
        if not spec:
            raise ValueError("Missing job")
        if spec.get("status") in {"done", "partial"}:
            return

        outputs = {}
        reports = {}
        source_published = False

        def language_done(run_dir, lang, report):
            nonlocal source_published
            src = report.get("src") or spec.get("src")
            urls = cloud.upload_outputs(run_dir, job_id, demo=bool(spec.get("demo")), lang=lang,
                                        include_source=src if not source_published else None)
            cloud.publish_results(run_dir, job_id, [lang], lease_token=lease_token)
            outputs.update(urls)
            source_published = source_published or bool(src)
            reports[lang] = report
            if not fenced_update(ref, lease_token, {"outputs": dict(outputs), "completed_langs": list(reports),
                        "language_reports": dict(reports), "src": src, "updated": time.time()}):
                raise RuntimeError("Worker lease expired")

        run_dir = pipeline.main(spec["url"], spec.get("langs") or None, spec.get("max_sec"),
                                on_language_done=language_done)
        outputs.update(cloud.upload_outputs(run_dir, job_id, demo=bool(spec.get("demo")),
                                            skip_names=set(outputs) - {"report.json"}))
        report = json.loads((run_dir / "out" / "report.json").read_text())
        cloud.publish_results(run_dir, job_id, [r["lang"] for r in report["langs"]], lease_token=lease_token)
        can_edit = False
        try:
            workspace = cloud.save_workspace(run_dir, job_id)
            cloud.access(job_id).update({"workspace": workspace})
            can_edit = True
        except Exception:
            # Publishing a usable dub must not depend on edit-storage availability.
            traceback.print_exc()
        status = "partial" if report.get("failures") else "done"
        if not report.get("langs"):
            status = "error"
        fenced_update(ref, lease_token, {"status": status, "stage": {"partial": "Some languages need another try", "error": "No languages finished", "done": "Done"}[status],
                    "outputs": outputs, "report": report, "src": report.get("src"), "can_regenerate": can_edit and bool(report.get("langs")),
                    "finished": time.time()})
    except Exception:
        fenced_update(progress, lease_token, {"status": "error", "error": "The preview could not finish. Discard it to try again." if edit_id else ERROR,
                         "finished": time.time()})
        traceback.print_exc()
        raise
    finally:
        stop.set()
        thread.join(timeout=2)
        if sink in events._sinks:
            events._sinks.remove(sink)


if __name__ == "__main__":
    run(os.environ["JOB_ID"], os.environ.get("EDIT_ID"))
