"""Review a deterministic showcase publication; dry-run unless --execute plus fingerprint.

No synthesis, deletion, legacy-job overwrite, or Cloud Run execution. Uploads become public
by link during staging; listing/featured flags are enabled only after all writes finish.
"""
import argparse
import hashlib
import json
import re
import subprocess
import shutil
import tempfile
import time
from pathlib import Path

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from google.oauth2.credentials import Credentials

from dub import cloud, config

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "review-sample-v1"
PROJECT = "viberick"
ACCOUNT = "jaeho.shin@viberick.com"
PUBLIC_BUCKET = "viberick-dub-public"
FIELDS = ("title", "src", "url", "source_interval", "voice_disclosure", "alignment_provenance",
          "validation_scope", "source_captioned", "speakers")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_public_data(value):
    """Fail closed instead of uploading internal absolute paths hidden in report/event fields."""
    if isinstance(value, dict):
        for item in value.values():
            require_public_data(item)
    elif isinstance(value, list):
        for item in value:
            require_public_data(item)
    elif isinstance(value, str):
        if value.startswith(("/", "file://")) or re.search(r"/(?:Users|home|tmp|mnt|app)/|[A-Za-z]:\\", value):
            raise ValueError("Publication metadata contains an internal absolute path")


def build_plan(run_dir: Path, manifest_path: Path):
    manifest = json.loads(manifest_path.read_text())
    job = manifest["job"]
    report = json.loads((run_dir / "out/report.json").read_text())
    if report != job["report"]:
        raise ValueError("Reviewed manifest and final run report differ")
    metadata = {field: job[field] for field in FIELDS}
    video = report["video"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("Invalid source video id")
    langs = job["langs"]
    if not langs or len(langs) != len(set(langs)) or set(langs) != {r["lang"] for r in report["langs"]}:
        raise ValueError("Manifest language list differs from final report")
    interval = metadata["source_interval"]
    if abs(interval["end"] - interval["start"] - report["duration"]) > .001:
        raise ValueError("Source interval differs from exported clip duration")
    if not metadata["voice_disclosure"] or not metadata["alignment_provenance"] or not metadata["validation_scope"]:
        raise ValueError("Voice, alignment and validation disclosures are required")
    if not metadata["speakers"] or any(s.get("voice_type") != "preset" for s in metadata["speakers"].values()):
        raise ValueError("This prepared public-figure sample must disclose preset voices")
    lines = {lang: cloud.result_document(run_dir, lang) for lang in langs}
    if lines != manifest["lines"]:
        raise ValueError("Reviewed manifest rows differ from final run rows")
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines() if line.strip()]
    if events != manifest["events"]:
        raise ValueError("Reviewed manifest events differ from final run events")
    expected = {"video.orig.mp4", "report.json", f"subs.{job['src']}.srt", f"subs.{job['src']}.vtt"}
    for lang in langs:
        expected.update({f"video.{lang}.mp4", f"dub.{lang}.m4a", f"subs.{lang}.srt", f"subs.{lang}.vtt", f"timeline.{lang}.json"})
    outputs = job["outputs"]
    if set(outputs) != expected or any(name != value for name, value in outputs.items()):
        raise ValueError("Manifest must reference exactly the prepared local output filenames")
    actual_files = list((run_dir / "out").iterdir())
    if {p.name for p in actual_files} != expected or any(not p.is_file() or p.is_symlink() for p in actual_files):
        raise ValueError("Output directory differs from the reviewed publication file set")
    files = []
    for path in sorted(actual_files):
        if path.suffix == ".json":
            require_public_data(json.loads(path.read_text()))
        files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest_file(path)})
    payload = {"schema": SCHEMA, "video": video, "metadata": metadata, "report": report,
               "langs": langs, "lines": lines, "events": events, "files": files}
    require_public_data(payload)
    fingerprint = hashlib.sha256(canonical(payload)).hexdigest()
    job_id = f"sample-{video}-{fingerprint[:24]}"
    return {"job_id": job_id, "fingerprint": fingerprint, "payload": payload,
            "plan": {"mode": "dry_run", "job_id": job_id, "fingerprint": fingerprint,
                     "public_prefix": f"gs://{PUBLIC_BUCKET}/demo/{job_id}/", "metadata": metadata,
                     "languages": langs, "duration_seconds": report["duration"],
                     "line_count": sum(len(doc["rows"]) for doc in lines.values()),
                     "event_count": len(events), "file_count": len(files), "bytes": sum(f["bytes"] for f in files),
                     "files": files, "initial_visibility": {"demo": False, "featured": False},
                     "final_visibility": {"demo": True, "featured": True, "can_regenerate": False},
                     "note": "No network calls in dry-run. Execution makes files public by link before enabling showcase listing."}}


def ensure_same(existing, plan):
    if existing and (existing.get("publication_fingerprint") != plan["fingerprint"] or existing.get("publisher_schema") != SCHEMA):
        raise ValueError("Existing job is not this exact publication; refusing overwrite")


def event_id(index, event):
    return f"{index:06d}-{hashlib.sha256(canonical(event)).hexdigest()[:20]}"


def publish(plan, run_dir):
    """Only called after explicit execution approval; matching interrupted runs can resume."""
    ref = cloud.job(plan["job_id"])
    existing = ref.get().to_dict()
    ensure_same(existing, plan)
    if existing and existing.get("status") == "done" and existing.get("demo") is True and existing.get("featured") is True:
        return {"job_id": plan["job_id"], "status": "already_published", "fingerprint": plan["fingerprint"]}
    payload = plan["payload"]
    if not existing:
        record = {**payload["metadata"], "video": payload["video"], "langs": payload["langs"],
                  "max_sec": payload["report"]["duration"], "status": "publishing", "stage": "Publishing reviewed sample",
                  "demo": False, "featured": False, "can_regenerate": False, "revision": 0,
                  "publication_fingerprint": plan["fingerprint"], "publisher_schema": SCHEMA, "created": time.time(),
                  "thumbnail": f"https://i.ytimg.com/vi/{payload['video']}/hqdefault.jpg"}
        try:
            ref.create(record)
        except AlreadyExists:
            ensure_same(ref.get().to_dict(), plan)
    # Stable creates preserve existing event documents, including on interrupted reruns.
    for index, event in enumerate(payload["events"]):
        event_ref = ref.collection("events").document(event_id(index, event))
        try:
            event_ref.create(event)
        except AlreadyExists:
            if event_ref.get().to_dict() != event:
                raise ValueError("Existing event differs; refusing overwrite")
    for lang, data in payload["lines"].items():
        previous = ref.collection("lines").document(lang).get().to_dict()
        if previous is not None and previous != data:
            raise ValueError("Existing review rows differ; refusing overwrite")
    cloud.publish_results(run_dir, plan["job_id"], payload["langs"])
    urls = cloud.upload_outputs(run_dir, plan["job_id"], demo=True)
    if set(urls) != {f["name"] for f in payload["files"]}:
        raise ValueError("Not every reviewed output was uploaded; showcase remains unlisted")
    # Recheck the immutable fingerprint immediately before the visibility switch.
    @firestore.transactional
    def finish(tx):
        ensure_same(ref.get(transaction=tx).to_dict(), plan)
        tx.update(ref, {"status": "done", "stage": "Done", "demo": True, "featured": True,
                        "can_regenerate": False, "outputs": urls, "report": payload["report"],
                        "completed_langs": payload["langs"], "finished": time.time()})
    finish(cloud.db().transaction())
    return {"job_id": plan["job_id"], "status": "published", "fingerprint": plan["fingerprint"],
            "url": f"https://viberick-dub.web.app/?job={plan['job_id']}"}


def explicit_credentials():
    token = subprocess.run(["gcloud", "auth", "print-access-token", f"--project={PROJECT}", f"--account={ACCOUNT}"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return Credentials(token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "runs/podcast-demo-2026-10-11")
    parser.add_argument("--manifest", type=Path, default=ROOT / "web/review/podcast/manifest.json")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved-fingerprint")
    parser.add_argument("--plan-output", type=Path)
    args = parser.parse_args()
    plan = build_plan(args.run, args.manifest)
    if args.plan_output:
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.plan_output.write_text(json.dumps(plan["plan"], ensure_ascii=False, indent=2) + "\n")
    if not args.execute:
        print(json.dumps(plan["plan"], ensure_ascii=False, indent=2))
        return
    if args.approved_fingerprint != plan["fingerprint"]:
        parser.error("Execution requires the exact --approved-fingerprint from the reviewed dry run")
    if config.GCP_PROJECT != PROJECT or cloud.PUBLIC_BUCKET != PUBLIC_BUCKET:
        parser.error("Only the VibeRick project and public output bucket are allowed")
    config.gcp_credentials = explicit_credentials
    cloud._db = None
    # Recompute after validation so changed media cannot silently use an earlier approval.
    if build_plan(args.run, args.manifest)["fingerprint"] != plan["fingerprint"]:
        parser.error("Inputs changed during publication preparation")
    # Freeze exactly the reviewed publication inputs; concurrent local editing cannot
    # change media or rows between fingerprint validation and cloud upload.
    with tempfile.TemporaryDirectory(prefix="review-sample-") as temporary:
        staged = Path(temporary)
        (staged / "out").mkdir()
        (staged / "dub").mkdir()
        for item in plan["payload"]["files"]:
            shutil.copy2(args.run / "out" / item["name"], staged / "out" / item["name"])
        for name in ("units.json", "events.jsonl"):
            shutil.copy2(args.run / name, staged / name)
        for lang in plan["payload"]["langs"]:
            shutil.copy2(args.run / "dub" / f"{lang}.json", staged / "dub" / f"{lang}.json")
        shutil.copy2(args.manifest, staged / "manifest.json")
        staged_plan = build_plan(staged, staged / "manifest.json")
        if staged_plan["fingerprint"] != plan["fingerprint"]:
            parser.error("Inputs changed while freezing publication files")
        print(json.dumps(publish(staged_plan, staged), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
