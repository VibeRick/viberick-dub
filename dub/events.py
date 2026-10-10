"""Append-only agent event log. The web UI tails this file / mirrors it to Firestore."""
import json
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_sinks: list = []   # callables(run_dir, event) — e.g. the Firestore mirror on Cloud Run


def log(run_dir: Path, kind: str, **data) -> None:
    ev = {"t": round(time.time(), 3), "kind": kind, **data}
    with _lock, open(run_dir / "events.jsonl", "a") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    for s in _sinks:
        try:
            s(run_dir, ev)
        except Exception:  # noqa: BLE001  a UI mirror must never break the pipeline
            pass
