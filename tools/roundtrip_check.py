"""Independent check of a finished cloud job: Chirp 3 transcribes every dubbed line back and the
result is compared with the line the agent meant to say (character error rate, CER).

Gemini already listens to each line inside the pipeline; this is a second opinion from a different
model, so a language we cannot hear ourselves (Hindi, Tamil, …) is not graded only by its author.

  PYTHONPATH=. uv run python -m tools.roundtrip_check JOB_ID hi ta es
"""
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

from dub import config, stt

CHIRP = {"hi": "hi-IN", "ta": "ta-IN", "es": "es-US", "bn": "bn-IN", "te": "te-IN", "mr": "mr-IN",
         "fr": "fr-FR", "de": "de-DE", "pt": "pt-BR", "id": "id-ID", "ar": "ar-EG", "vi": "vi-VN", "th": "th-TH"}
FS = "https://firestore.googleapis.com/v1/projects/{p}/databases/(default)/documents/jobs/{j}"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {config.gcp_token()}"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _plain(v: dict):
    """Firestore REST value → Python."""
    (kind, x), = v.items()
    if kind == "mapValue":
        return {k: _plain(y) for k, y in x.get("fields", {}).items()}
    if kind == "arrayValue":
        return [_plain(y) for y in x.get("values", [])]
    if kind in ("integerValue",):
        return int(x)
    return x


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in "LMN")


def cer(ref: str, hyp: str) -> float:
    a, b = norm(ref), norm(hyp)
    if not a:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def check(job: str, lang: str, work: Path) -> dict:
    base = FS.format(p=config.GCP_PROJECT, j=job)
    doc = {k: _plain(v) for k, v in _get(base)["fields"].items()}
    rows = _plain({"arrayValue": _get(f"{base}/lines/{lang}")["fields"]["rows"]["arrayValue"]})
    audio = work / f"dub.{lang}.m4a"
    urllib.request.urlretrieve(doc["outputs"][f"dub.{lang}.m4a"], audio)
    config.CHIRP_CODES[lang] = CHIRP.get(lang) or config.CHIRP_CODES[lang]
    out = []
    for r in rows:
        a, b = float(r["dub_start"]), float(r["dub_end"])
        wav = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(a), "-to", str(b), "-i", str(audio),
                              "-ac", "1", "-ar", "16000", "-f", "wav", "-"], capture_output=True, check=True).stdout
        heard = " ".join(w["w"] for w in stt.chirp_sync_words(wav, lang))
        out.append({"id": r["id"], "said": r["text"], "chirp": heard, "cer": round(cer(r["text"], heard), 3),
                    "gemini_ok": r.get("ok")})
    mean = sum(x["cer"] for x in out) / len(out)
    median = sorted(x["cer"] for x in out)[len(out) // 2]
    return {"lang": lang, "lines": len(out), "mean_cer": round(mean, 3), "median_cer": median,
            "over_30pct": sum(x["cer"] > 0.3 for x in out), "rows": out}


if __name__ == "__main__":
    job, langs = sys.argv[1], sys.argv[2:]
    with tempfile.TemporaryDirectory() as d:
        res = [check(job, l, Path(d)) for l in langs]
    dest = config.ROOT / "docs" / "validation" / f"roundtrip-{job}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res:
        print(f"{r['lang']}: {r['lines']} lines · median CER {r['median_cer']:.1%} · mean {r['mean_cer']:.1%} · {r['over_30pct']} lines over 30%")
    print(dest)
