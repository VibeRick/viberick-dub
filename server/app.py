"""VibeRick Dub API (Cloud Run service). Creates jobs in Firestore and starts the worker Cloud Run Job.
The web app (Firebase Hosting) reads job progress straight from Firestore."""
import os
import hashlib
import json
import hmac
import secrets
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header
from google.cloud import run_v2, firestore
from pydantic import BaseModel, Field

from dub import cloud, config, fetch

REGION = os.environ.get("DUB_REGION", "asia-northeast3")
WORKER = os.environ.get("DUB_WORKER_JOB", "viberick-dub-worker")
DAILY_CAP = int(os.environ.get("DUB_DAILY_CAP", "40"))
EDIT_CAP = int(os.environ.get("DUB_JOB_EDIT_CAP", "5"))
LEASE_SEC = 180
QUEUE_TIMEOUT_SEC = 600
PUBLIC_MAX_SEC = 180
YT = re.compile(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")

app = FastAPI(title="VibeRick Dub")


class JobIn(BaseModel):
    url: str
    langs: list[str] = Field(default_factory=list)
    max_sec: float = Field(default=PUBLIC_MAX_SEC, gt=0, allow_inf_nan=False)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/jobs")
def create_job(j: JobIn, idempotency_key: str | None = Header(default=None, max_length=128),
               x_job_token: str | None = Header(default=None, min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")):
    if not YT.match(j.url) or not fetch._ID.search(j.url):   # one video only; never run yt-dlp here
        raise HTTPException(400, "Paste a link to one YouTube video.")
    langs = list(dict.fromkeys(j.langs))
    bad = [l for l in langs if l not in config.LANGS]
    if bad:
        raise HTTPException(400, f"Unsupported language: {', '.join(bad)}")
    if len(langs) > config.MAX_LANGS_PER_JOB:
        raise HTTPException(400, f"Pick up to {config.MAX_LANGS_PER_JOB} languages per video.")
    vid = fetch._ID.search(j.url).group(1)
    source_url = f"https://www.youtube.com/watch?v={vid}"
    job_id = f"{vid}-{uuid.uuid4().hex[:6]}"
    max_sec = min(j.max_sec, PUBLIC_MAX_SEC)
    owner_token = x_job_token or secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(owner_token.encode()).hexdigest()
    payload_hash = hashlib.sha256(json.dumps({"url": source_url, "langs": sorted(langs), "max_sec": max_sec},
                                            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    @firestore.transactional
    def reserve(tx):
        request_ref = (cloud.db().collection("quotas").document("request-" + hashlib.sha256(idempotency_key.encode()).hexdigest())
                       if idempotency_key else None)
        previous = request_ref.get(transaction=tx).to_dict() if request_ref else None
        if previous:
            access = cloud.access(previous["job_id"]).get(transaction=tx).to_dict() or {}
            if not x_job_token or not hmac.compare_digest(token_hash, access.get("token_hash", "")):
                raise HTTPException(403, "The original job token is required to recover this request.")
            if previous.get("payload_hash") != payload_hash:
                raise HTTPException(409, "This request key belongs to a different dubbing request.")
            return {"id": previous["job_id"], "owner_token": owner_token,
                    "revision": access.get("revision", 0), "replayed": True}
        quota_ref, used = quota(tx)
        tx.set(quota_ref, {"operations": used + 1})
        if request_ref:
            tx.set(request_ref, {"created": time.time(), "job_id": job_id, "payload_hash": payload_hash})
        tx.set(cloud.access(job_id), {"token_hash": token_hash, "revision": 0,
                                    "edit_count": 0})
        tx.set(cloud.job(job_id), {"url": source_url, "video": vid, "langs": langs, "max_sec": max_sec, "status": "queued",
                                 "stage": "Queued", "created": time.time(), "demo": False, "revision": 0,
                                 "can_regenerate": False, "edits_remaining": EDIT_CAP,
                                 "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
    recovered = reserve(cloud.db().transaction())
    if recovered:
        return recovered
    try:
        launch(job_id)
    except Exception as e:  # noqa: BLE001  the UI must not show a job stuck in "queued"
        cloud.job(job_id).update({"status": "error", "error": "The dubbing worker could not start. Try again."})
        raise HTTPException(503, "The dubbing worker could not start. Try again in a minute.") from e
    return {"id": job_id, "owner_token": owner_token, "revision": 0}



def quota(tx):
    ref = cloud.db().collection("quotas").document("operations-" + datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    used = (ref.get(transaction=tx).to_dict() or {}).get("operations", 0)
    if used >= DAILY_CAP:
        raise HTTPException(429, "Daily demo operation capacity reached. Try a finished example.")
    return ref, used


def launch(job_id: str, edit_id: str | None = None):
    env = [run_v2.EnvVar(name="JOB_ID", value=job_id)]
    if edit_id:
        env.append(run_v2.EnvVar(name="EDIT_ID", value=edit_id))
    return run_v2.JobsClient().run_job(run_v2.RunJobRequest(
        name=f"projects/{config.GCP_PROJECT}/locations/{REGION}/jobs/{WORKER}",
        overrides=run_v2.RunJobRequest.Overrides(container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(env=env)])))


class RevisionIn(BaseModel):
    revision: int = Field(ge=0)


class EditIn(RevisionIn):
    text: str = Field(min_length=1, max_length=2000)


def owner(job_id: str, token: str | None):
    ref = cloud.access(job_id)
    data = ref.get().to_dict() or {}
    supplied = hashlib.sha256((token or "").encode()).hexdigest()
    if not token or not hmac.compare_digest(supplied, data.get("token_hash", "")):
        raise HTTPException(403, "Only the creator of this job can edit it.")
    return ref


@app.post("/api/jobs/{job_id}/lines/{lang}/{line_id}/regenerate")
def regenerate(job_id: str, lang: str, line_id: int, body: EditIn,
               x_job_token: str | None = Header(default=None)):
    access_ref = owner(job_id, x_job_token)
    if not body.text.strip():
        raise HTTPException(422, "Enter the text to speak.")
    ref = cloud.job(job_id)
    spec = ref.get().to_dict() or {}
    rows = (ref.collection("lines").document(lang).get().to_dict() or {}).get("rows", [])
    if lang not in config.LANGS or not any(r["id"] == line_id for r in rows):
        raise HTTPException(404, "This language or line is unavailable.")
    if not spec.get("can_regenerate") or spec.get("status") not in {"done", "partial"}:
        raise HTTPException(409, "Wait until the job has finished before editing.")
    edit_id = uuid.uuid4().hex
    edit_ref = ref.collection("edits").document(edit_id)

    @firestore.transactional
    def reserve(tx):
        access_data = access_ref.get(transaction=tx).to_dict()
        if access_data.get("revision", 0) != body.revision:
            raise HTTPException(409, "This job changed. Reload before editing.")
        if access_data.get("active_edit"):
            raise HTTPException(409, "Accept or discard the current preview first.")
        edits = access_data.get("edit_count", 0)
        if edits >= EDIT_CAP:
            raise HTTPException(429, "This job has reached its preview limit.")
        quota_ref, used = quota(tx)
        tx.set(quota_ref, {"operations": used + 1})
        tx.update(access_ref, {"active_edit": edit_id, "edit_count": edits + 1})
        tx.update(ref, {"edits_remaining": EDIT_CAP - edits - 1})
        tx.set(edit_ref, {"status": "queued", "lang": lang, "line_id": line_id, "text": body.text.strip(),
                          "revision": body.revision, "created": time.time()})
    reserve(cloud.db().transaction())
    try:
        launch(job_id, edit_id)
    except Exception as exc:
        edit_ref.update({"status": "error", "error": "The preview worker could not start."})
        # Keep the failed draft reserved so the owner can discard it after reconnecting.
        raise HTTPException(503, "The preview worker could not start. Discard the failed draft to try again.") from exc
    return {"edit_id": edit_id, "status": "queued", "revision": body.revision}


@app.post("/api/jobs/{job_id}/edits/{edit_id}/accept")
def accept_edit(job_id: str, edit_id: str, body: RevisionIn, x_job_token: str | None = Header(default=None)):
    access_ref = owner(job_id, x_job_token)
    ref = cloud.job(job_id)
    edit_ref = ref.collection("edits").document(edit_id)
    private_ref = access_ref.collection("edits").document(edit_id)

    @firestore.transactional
    def accept(tx):
        access_data = access_ref.get(transaction=tx).to_dict() or {}
        edit = edit_ref.get(transaction=tx).to_dict() or {}
        private = private_ref.get(transaction=tx).to_dict() or {}
        spec = ref.get(transaction=tx).to_dict() or {}
        if (access_data.get("revision", 0) != body.revision or access_data.get("active_edit") != edit_id
                or edit.get("status") != "ready" or not private.get("workspace")):
            raise HTTPException(409, "This preview is not ready or has been superseded.")
        revision = body.revision + 1
        report = dict(spec.get("report") or {})
        report["langs"] = [edit["report"] if r["lang"] == edit["lang"] else r for r in report.get("langs", [])]
        tx.update(ref, {"revision": revision, "outputs": {**spec.get("outputs", {}), **edit["outputs"]},
                        "report": report, "updated": time.time()})
        tx.set(ref.collection("lines").document(edit["lang"]), private["result"])
        tx.update(access_ref, {"revision": revision, "active_edit": None, "workspace": private["workspace"]})
        tx.update(edit_ref, {"status": "accepted", "accepted": time.time()})
    accept(cloud.db().transaction())
    return {"status": "accepted", "revision": body.revision + 1}


@app.post("/api/jobs/{job_id}/edits/{edit_id}/discard")
def discard_edit(job_id: str, edit_id: str, body: RevisionIn, x_job_token: str | None = Header(default=None)):
    access_ref = owner(job_id, x_job_token)
    edit_ref = cloud.job(job_id).collection("edits").document(edit_id)

    @firestore.transactional
    def discard(tx):
        data = access_ref.get(transaction=tx).to_dict() or {}
        edit = edit_ref.get(transaction=tx).to_dict() or {}
        if data.get("revision", 0) != body.revision or data.get("active_edit") != edit_id:
            raise HTTPException(409, "This preview has been superseded.")
        if edit.get("status") in {"queued", "running"} and not expired(edit):
            raise HTTPException(409, "Wait for the preview to finish.")
        tx.update(access_ref, {"active_edit": None})
        tx.update(edit_ref, {"status": "discarded", "lease_token": None})
    discard(cloud.db().transaction())
    return {"status": "discarded", "revision": body.revision}


def expired(data):
    if data.get("status") == "queued":
        return time.time() > data.get("created", time.time()) + QUEUE_TIMEOUT_SEC
    return time.time() > data.get("lease_until", data.get("heartbeat", data.get("started", time.time())) + LEASE_SEC)


@app.post("/api/jobs/{job_id}/reconcile")
def reconcile(job_id: str, x_job_token: str | None = Header(default=None)):
    """Owner-triggered lease expiry recovery; a late worker is fenced from publishing."""
    access_ref = owner(job_id, x_job_token)
    ref = cloud.job(job_id)
    @firestore.transactional
    def recover(tx):
        private = access_ref.get(transaction=tx).to_dict() or {}
        data = ref.get(transaction=tx).to_dict() or {}
        edit_ref = ref.collection("edits").document(private["active_edit"]) if private.get("active_edit") else None
        edit = edit_ref.get(transaction=tx).to_dict() if edit_ref else None
        changed = False
        for target, value in ((ref, data), (edit_ref, edit)):
            if target and value and value.get("status") in {"queued", "running"} and expired(value):
                tx.update(target, {"status": "error", "lease_token": None,
                                   "error": "The worker stopped reporting progress. Its lease expired.", "finished": time.time()})
                changed = True
        return changed
    return {"recovered": recover(cloud.db().transaction())}
