"""Bounded release smoke. Private state stays in ignored runs/. No automatic retries/new jobs."""
import argparse
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import httpx
from google.cloud import firestore
from google.oauth2.credentials import Credentials

from dub.budget import Budget

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "runs/cloud-smoke-2026-10-11/state.json"
PROJECT = "viberick"
ACCOUNT = "jaeho.shin@viberick.com"


def save(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2)


def database():
    result = subprocess.run(["gcloud", "auth", "print-access-token", f"--project={PROJECT}", f"--account={ACCOUNT}"],
                            capture_output=True, text=True, check=True)
    return firestore.Client(project=PROJECT, credentials=Credentials(result.stdout.strip()))


def request(state, path, body=None, token=True):
    headers = {"X-Job-Token": state["owner_token"]} if token else {}
    response = httpx.post(state["base"] + path, json=body, headers=headers, timeout=60)
    if response.status_code >= 400:
        raise RuntimeError(f"{path}: HTTP {response.status_code}: {response.json().get('detail', '')}")
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "create", "status", "preview", "accept", "discard", "verify"])
    parser.add_argument("--base")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--text", help="Optional reviewed replacement text for a single preview")
    parser.add_argument("--revalidation", action="store_true", help="One authorized additional exact-text preview; reserves $5")
    args = parser.parse_args()
    if args.action == "prepare":
        if STATE.exists():
            raise SystemExit("State already exists; reuse this run instead of starting another")
        if not args.base or not args.base.startswith("https://review---viberick-dub-") or not args.base.endswith(".a.run.app"):
            raise SystemExit("Use the reviewed Cloud Run tag URL")
        state = {"base": args.base.rstrip("/"), "owner_token": secrets.token_urlsafe(32),
                 "idempotency_key": secrets.token_urlsafe(24),
                 "body": {"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"], "max_sec": 12},
                 "preview_count": 0, "created": time.time()}
        save(state)
        print(json.dumps({"prepared": True, "seconds": 12, "language": "en", "max_previews": 2,
                          "aggregate_allowance_usd": 10, "state": str(STATE)}))
        return
    state = json.loads(STATE.read_text())
    if args.action in {"create", "preview", "accept", "discard"} and not args.execute:
        raise SystemExit("Explicit --execute is required")
    if args.action == "create":
        if not state.get("budget_reserved"):
            budget = Budget(100, {"tts": 500, "text": 500}, ROOT / "runs/validation-budget-2026-10-10.json", run_cap_usd=10)
            budget.reserve("text", 10)
            state["budget_reserved"] = True
            save(state)
        headers = {"X-Job-Token": state["owner_token"], "Idempotency-Key": state["idempotency_key"]}
        response = httpx.post(state["base"] + "/api/jobs", json=state["body"], headers=headers, timeout=60)
        response.raise_for_status()
        first = response.json()
        state["job_id"] = first["id"]
        save(state)
        retry = httpx.post(state["base"] + "/api/jobs", json=state["body"], headers=headers, timeout=60)
        retry.raise_for_status()
        assert retry.json()["id"] == first["id"] and retry.json().get("replayed")
        denied = httpx.post(state["base"] + f"/api/jobs/{first['id']}/lines/en/0/regenerate",
                            json={"text": "Unauthorized probe", "revision": 0}, timeout=30)
        assert denied.status_code == 403
        state["idempotency_verified"] = state["owner_verified"] = True
        save(state)
        print(json.dumps({"job_id": first["id"], "replay": "same job", "unauthorized": denied.status_code}))
        return
    db = database()
    ref = db.collection("jobs").document(state["job_id"])
    job = ref.get().to_dict()
    if args.action == "status":
        events = [doc.to_dict() for doc in ref.collection("events").stream()]
        edit = ref.collection("edits").document(state["edit_id"]).get().to_dict() if state.get("edit_id") else None
        print(json.dumps({"job_id": state["job_id"], "status": job.get("status"), "stage": job.get("stage"),
                          "src": job.get("src"), "heartbeat": job.get("heartbeat"), "revision": job.get("revision"),
                          "outputs": list(job.get("outputs", {})), "can_regenerate": job.get("can_regenerate"),
                          "error": job.get("error"), "synth_events": sum(ev.get("do") == "synth" for ev in events),
                          "repair_events": sum(ev.get("do") in {"resynth", "retranslate", "shorten", "lengthen"} for ev in events),
                          "preview": {k: edit.get(k) for k in ("status", "error", "heartbeat", "revision")} if edit else None}))
    elif args.action == "preview":
        limit = 3 if args.revalidation else 2
        if args.revalidation and not args.text:
            raise SystemExit("Exact-text revalidation requires --text")
        if state["preview_count"] >= limit or job.get("status") != "done" or not job.get("can_regenerate"):
            raise SystemExit("Preview cap reached or job unavailable")
        if args.revalidation and not state.get("revalidation_reserved"):
            budget = Budget(100, {"tts": 500, "text": 500}, ROOT / "runs/validation-budget-2026-10-10.json", run_cap_usd=5)
            budget.reserve("text", 5)
            state["revalidation_reserved"] = True
            save(state)
        rows = ref.collection("lines").document("en").get().to_dict()["rows"]
        row = rows[0]
        state["before_outputs"] = job["outputs"]
        state["before_revision"] = job.get("revision", 0)
        state["requested_text"] = args.text or row["text"]
        state["assert_exact_text"] = args.revalidation
        save(state)
        result = request(state, f"/api/jobs/{state['job_id']}/lines/en/{row['id']}/regenerate",
                         {"text": args.text or row["text"], "revision": state["before_revision"]})
        state["edit_id"] = result["edit_id"]
        state["preview_count"] += 1
        save(state)
        print(json.dumps({"preview": result, "line_id": row["id"]}))
    elif args.action in {"accept", "discard"}:
        edit = ref.collection("edits").document(state["edit_id"]).get().to_dict()
        if edit.get("status") != "ready":
            raise SystemExit("Preview not ready")
        assert job["outputs"] == state["before_outputs"]
        if state.get("assert_exact_text"):
            assert edit["row"]["text"] == state["requested_text"], "Generated wording differs from submitted edit"
            checks = [a for a in edit["row"].get("actions", []) if a.get("do") == "check"]
            assert checks and checks[-1]["ok"] is True, "Exact-text preview failed automated audio checks"
            state["exact_text_timing_issue"] = edit["row"].get("issue", "")
            state["exact_text_actual"] = edit["row"]["text"]
            state["exact_text_verified"] = True
        path = f"/api/jobs/{state['job_id']}/edits/{state['edit_id']}/{args.action}"
        result = request(state, path, {"revision": state["before_revision"]})
        state[args.action + "_verified"] = True
        save(state)
        print(json.dumps(result))
    elif args.action == "verify":
        rows = ref.collection("lines").document("en").get().to_dict()["rows"]
        outputs = job["outputs"]
        required = {"video.orig.mp4", "subs.ko.vtt", "dub.en.m4a", "video.en.mp4", "subs.en.vtt", "timeline.en.json"}
        assert required <= outputs.keys() and job["src"] == "ko"
        for row in rows:
            assert {"source_start", "source_end", "start", "end"} <= row.keys()
            assert row["end"] > row["start"]
        checks = {}
        for name in required:
            response = httpx.get(outputs[name], headers={"Range": "bytes=0-1023"}, timeout=60)
            response.raise_for_status()
            checks[name] = response.status_code
        evidence = {"job_id": state["job_id"], "base": state["base"], "duration": job["report"]["duration"],
                    "status": job["status"], "revision": job.get("revision", 0), "rows": len(rows),
                    "artifact_checks": checks, "tts_calls": job["report"].get("tts_calls"),
                    "verified": {k: v for k, v in state.items() if k.endswith("_verified")},
                    "exact_text_timing_issue": state.get("exact_text_timing_issue", ""),
                    "exact_text_requested": state.get("requested_text") if state.get("exact_text_verified") else None,
                    "exact_text_actual": state.get("exact_text_actual"),
                    "aggregate_reserved_usd": 15 if state.get("revalidation_reserved") else 10,
                    "budget_note": "Conservative aggregate cloud allowance, not measured billing or per-call count."}
        (STATE.parent / "evidence.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence))


if __name__ == "__main__":
    main()
