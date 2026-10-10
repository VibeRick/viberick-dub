"""Firestore job documents, live event mirror, and public GCS outputs (used on Cloud Run).

Schema: jobs/{id} = {url, langs, max_sec, status, stage, title, thumbnail, src, voice, outputs, report, ...}
        jobs/{id}/events/{auto}  = one agent event each (the UI's live log)
        jobs/{id}/lines/{lang}   = {rows: [...]} per-line results for the review table"""
import json
import mimetypes
import os
import time
from pathlib import Path

from google.cloud import firestore, storage

from . import config

PUBLIC_BUCKET = os.environ.get("DUB_PUBLIC_BUCKET", "viberick-dub-public")
STAGES = {"start": "Downloading", "voice": "Checking voice consent", "separated": "Separating voice and music",
          "transcribed": "Transcribing (Chirp 3)", "proofread": "Proofreading (Gemini)",
          "brief": "Writing the dubbing brief", "translated": "Translating to fit timing",
          "voiced": "Speaking in the creator's voice", "language_done": "Mixing", "done": "Done"}
_db = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials())
    return _db


def job(job_id: str):
    return db().collection("jobs").document(job_id)


def event_sink(job_id: str):
    ref = job(job_id)

    def sink(run_dir: Path, ev: dict) -> None:
        ref.collection("events").add(ev)
        if ev["kind"] in STAGES:
            upd = {"stage": STAGES[ev["kind"]], "updated": time.time()}
            if ev["kind"] == "start":
                upd["title"] = ev.get("title")
            ref.update(upd)
    return sink


def upload_outputs(run_dir: Path, job_id: str) -> dict:
    bucket = storage.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials()).bucket(PUBLIC_BUCKET)
    urls = {}
    for p in sorted((run_dir / "out").iterdir()):
        blob = bucket.blob(f"jobs/{job_id}/{p.name}")
        ctype = "application/x-subrip" if p.suffix == ".srt" else mimetypes.guess_type(p.name)[0]
        blob.cache_control = "public, max-age=3600"
        blob.upload_from_filename(p, content_type=ctype)
        urls[p.name] = f"https://storage.googleapis.com/{PUBLIC_BUCKET}/{blob.name}"
    return urls


def publish_results(run_dir: Path, job_id: str, langs: list[str]) -> None:
    ref = job(job_id)
    units = json.loads((run_dir / "units.json").read_text())
    for lang in langs:
        data = json.loads((run_dir / "dub" / f"{lang}.json").read_text())
        ref.collection("lines").document(lang).set({"report": data["report"], "rows": [
            {**r, "start": u["start"], "end": u["end"], "src": u["text"], "spk": u.get("spk"),
             "voice": u.get("voice")} for u, r in zip(units, data["rows"])]})
