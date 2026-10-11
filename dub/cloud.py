"""Firestore job documents, live event mirror, and public GCS outputs (used on Cloud Run).

Schema: jobs/{id} = {url, langs, max_sec, status, stage, title, thumbnail, src, voice, outputs, report, ...}
        jobs/{id}/events/{auto}  = one agent event each (the UI's live log)
        jobs/{id}/lines/{lang}   = {rows: [...]} per-line results for the review table"""
import json
import mimetypes
import os
import tarfile
import tempfile
import time
from pathlib import Path

from google.cloud import firestore, storage

from . import config

PUBLIC_BUCKET = os.environ.get("DUB_PUBLIC_BUCKET", "viberick-dub-public")
STAGES = {"start": "Downloading", "voice": "Checking voice consent", "separated": "Separating voice and music",
          "transcribed": "Transcribing (Chirp 3)", "proofread": "Proofreading (Gemini)",
          "brief": "Writing the dubbing brief", "translated": "Translating to fit timing",
          "voiced": "Generating speech", "language_done": "Mixing", "done": "Done"}
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


def output_prefix(job_id: str, demo: bool) -> str:
    """Demo jobs live under demo/; everything else under jobs/, which a bucket lifecycle rule deletes after 7 days."""
    return f"{'demo' if demo else 'jobs'}/{job_id}"


def upload_outputs(run_dir: Path, job_id: str, demo: bool = False, *, lang: str | None = None,
                   revision: str | None = None, include_source: str | None = None,
                   skip_names: set[str] | None = None) -> dict:
    bucket = storage.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials()).bucket(PUBLIC_BUCKET)
    urls = {}
    allowed = {f"dub.{lang}.m4a", f"video.{lang}.mp4", f"subs.{lang}.srt", f"subs.{lang}.vtt",
               f"timeline.{lang}.json", "report.json"}
    if include_source:
        allowed.update({"video.orig.mp4", f"subs.{include_source}.srt", f"subs.{include_source}.vtt"})
    for p in sorted((run_dir / "out").iterdir()):
        if (not p.is_file() or p.name in (skip_names or set())
                or (lang and p.name not in allowed and not p.name.startswith(f"line.{lang}."))):
            continue
        prefix = output_prefix(job_id, demo)
        if revision:
            prefix += f"/revisions/{revision}"
        blob = bucket.blob(f"{prefix}/{p.name}")
        ctype = "application/x-subrip" if p.suffix == ".srt" else mimetypes.guess_type(p.name)[0]
        blob.cache_control = "public, max-age=3600"
        blob.upload_from_filename(p, content_type=ctype)
        urls[p.name] = f"https://storage.googleapis.com/{PUBLIC_BUCKET}/{blob.name}"
    return urls


def result_document(run_dir: Path, lang: str) -> dict:
    units = {u["id"]: u for u in json.loads((run_dir / "units.json").read_text())}
    data = json.loads((run_dir / "dub" / f"{lang}.json").read_text())
    rows = []
    for r in data["rows"]:
        u = units[r["id"]]
        start = r.get("start", r.get("dub_start", u["start"]))
        end = r.get("end", r.get("dub_end", start + r.get("dur", u["end"] - u["start"])))
        rows.append({**r, "source_start": u["start"], "source_end": u["end"],
                     "start": start, "end": end, "src": u["text"], "spk": u.get("spk"),
                     "voice": u.get("voice")})
    return {"report": data["report"], "rows": rows}


def publish_results(run_dir: Path, job_id: str, langs: list[str], lease_token: str | None = None) -> None:
    ref = job(job_id)
    documents = {lang: result_document(run_dir, lang) for lang in langs}
    if not lease_token:
        for lang, document in documents.items():
            ref.collection("lines").document(lang).set(document)
        return
    @firestore.transactional
    def publish(tx):
        data = ref.get(transaction=tx).to_dict() or {}
        if (data.get("lease_token") != lease_token or data.get("status") != "running"
                or data.get("lease_until", 0) < time.time()):
            raise RuntimeError("Worker lease expired")
        for lang, document in documents.items():
            tx.set(ref.collection("lines").document(lang), document)
    publish(db().transaction())


def access(job_id: str):
    return db().collection("job_access").document(job_id)


def save_workspace(run_dir: Path, job_id: str, revision: str = "initial") -> str:
    """Private resumable inputs; never upload these to the public output bucket."""
    if config.BUCKET == PUBLIC_BUCKET:
        raise ValueError("Private and public buckets must differ")
    name = f"workspaces/{job_id}/{revision}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "workspace.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for p in run_dir.rglob("*"):
                if (p.is_file() and not p.is_symlink()
                        and ("out" not in p.relative_to(run_dir).parts or p.relative_to(run_dir) == Path("out/report.json"))):
                    tar.add(p, arcname=str(p.relative_to(run_dir)), recursive=False)
        bucket = storage.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials()).bucket(config.BUCKET)
        bucket.blob(name).upload_from_filename(archive, content_type="application/gzip")
    return name


def load_workspace(name: str, destination: Path) -> None:
    if config.BUCKET == PUBLIC_BUCKET or not name.startswith("workspaces/"):
        raise ValueError("Invalid private workspace")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "workspace.tar.gz"
        bucket = storage.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials()).bucket(config.BUCKET)
        bucket.blob(name).download_to_filename(archive)
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter="data")
