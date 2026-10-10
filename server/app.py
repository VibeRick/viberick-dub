"""VibeRick Dub API (Cloud Run service). Creates jobs in Firestore and starts the worker Cloud Run Job.
The web app (Firebase Hosting) reads job progress straight from Firestore."""
import os
import re
import time
import uuid

from fastapi import FastAPI, HTTPException
from google.cloud import run_v2
from pydantic import BaseModel, Field

from dub import cloud, config, fetch

REGION = os.environ.get("DUB_REGION", "asia-northeast3")
WORKER = os.environ.get("DUB_WORKER_JOB", "viberick-dub-worker")
DAILY_CAP = int(os.environ.get("DUB_DAILY_CAP", "40"))
PUBLIC_MAX_SEC = 180
YT = re.compile(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")

app = FastAPI(title="VibeRick Dub")


class JobIn(BaseModel):
    url: str
    langs: list[str] = Field(default_factory=list)
    max_sec: float = PUBLIC_MAX_SEC


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/jobs")
def create_job(j: JobIn):
    if not YT.match(j.url) or not fetch._ID.search(j.url):   # one video only; never run yt-dlp here
        raise HTTPException(400, "Paste a link to one YouTube video.")
    langs = list(dict.fromkeys(j.langs))
    bad = [l for l in langs if l not in config.LANGS]
    if bad:
        raise HTTPException(400, f"Unsupported language: {', '.join(bad)}")
    since = time.time() - 86400
    if len(list(cloud.db().collection("jobs").where("created", ">", since).limit(DAILY_CAP).stream())) >= DAILY_CAP:
        raise HTTPException(429, "Daily demo capacity reached. Try one of the finished examples.")
    vid = fetch._ID.search(j.url).group(1)
    job_id = f"{vid}-{uuid.uuid4().hex[:6]}"
    max_sec = min(j.max_sec or PUBLIC_MAX_SEC, PUBLIC_MAX_SEC)
    cloud.job(job_id).set({"url": j.url, "video": vid, "langs": langs, "max_sec": max_sec, "status": "queued",
                           "stage": "Queued", "created": time.time(), "demo": False,
                           "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
    try:
        run_v2.JobsClient().run_job(run_v2.RunJobRequest(
            name=f"projects/{config.GCP_PROJECT}/locations/{REGION}/jobs/{WORKER}",
            overrides=run_v2.RunJobRequest.Overrides(container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(env=[run_v2.EnvVar(name="JOB_ID", value=job_id)])])))
    except Exception as e:  # noqa: BLE001  the UI must not show a job stuck in "queued"
        cloud.job(job_id).update({"status": "error", "error": "The dubbing worker could not start. Try again."})
        raise HTTPException(503, "The dubbing worker could not start. Try again in a minute.") from e
    return {"id": job_id}
