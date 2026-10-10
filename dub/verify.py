"""Speaker lock: is this diarized speaker the person who recorded consent?

Gemini cannot judge voice identity (it rated a stock preset 9/10 similar), so this one check uses an
open speaker-verification model (ECAPA-TDNN, speechbrain, CPU). Only the consenting person's embedding is
kept (never their audio), in the private bucket. A speaker gets the cloned voice only above THRESHOLD."""
import json
import os
import subprocess
from functools import cache
from pathlib import Path

THRESHOLD = float(os.environ.get("DUB_VERIFY_THRESHOLD", "0.45"))
REF_URI = os.environ.get("DUB_VOICE_EMBEDDING", "gs://viberick-dub-lab/voice/consent-speaker.ecapa.json")


@cache
def _model():
    from speechbrain.inference.speaker import EncoderClassifier
    return EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                          savedir=os.environ.get("DUB_ECAPA_DIR", "/tmp/ecapa"))


def embed(audio: Path) -> list[float]:
    import array
    import torch
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(audio), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    w = torch.tensor(array.array("h", raw), dtype=torch.float32).unsqueeze(0) / 32768.0
    with torch.no_grad():
        return _model().encode_batch(w).squeeze().tolist()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = sum(x * x for x in a) ** 0.5, sum(y * y for y in b) ** 0.5
    return dot / (na * nb)


def reference() -> list[float] | None:
    if p := os.environ.get("DUB_VOICE_EMBEDDING_FILE"):
        return json.loads(Path(p).read_text())
    from google.cloud import storage
    from . import config
    bucket, _, name = REF_URI.removeprefix("gs://").partition("/")
    blob = storage.Client(project=config.GCP_PROJECT, credentials=config.gcp_credentials()).bucket(bucket).blob(name)
    return json.loads(blob.download_as_text()) if blob.exists() else None


def speaker_sample(vocals: Path, units: list[dict], spk: str, out: Path, sec: float = 20.0) -> Path | None:
    segs, total = [], 0.0
    for u in sorted((u for u in units if (u.get("spk") or "1") == spk), key=lambda u: u["start"] - u["end"]):
        segs.append((u["start"], min(u["end"], u["start"] + sec - total)))
        total += segs[-1][1] - segs[-1][0]
        if total >= sec:
            break
    if not segs:
        return None
    flt = "".join(f"[0:a]atrim={a:.2f}:{b:.2f},asetpts=PTS-STARTPTS[s{i}];" for i, (a, b) in enumerate(segs))
    flt += "".join(f"[s{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vocals), "-filter_complex", flt, "-ac", "1",
                    "-ar", "16000", str(out)], check=True)
    return out
