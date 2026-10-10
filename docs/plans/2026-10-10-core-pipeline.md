# VibeRick Dub — Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One CLI command turns a YouTube URL into dubbed audio tracks in the creator's own cloned voice plus subtitles, for Korean, English, Japanese and Chinese, entirely on Google (Gemini + Chirp 3), with an agent that listens to every line and repairs failures.

**Architecture:** A cached, step-by-step pipeline in one run directory per video (`runs/<video_id>/`): fetch → separate → transcribe (Chirp 3 words + Gemini text fix, aligned back) → units → brief → per target language: translate to a time budget → synthesize in the cloned voice → fit → agent check-and-repair loop → place + mix → SRT. Every step writes a JSON/WAV artifact and is skipped when that artifact exists, so a crash or a prompt change reruns only what changed. The agent writes an event log (`events.jsonl`) that the later web UI streams.

**Tech Stack:** Python 3.12 + uv, google-genai (Vertex for text, Gemini API for replicated-voice TTS), google-cloud-speech (Chirp 3, `us`), google-cloud-storage, yt-dlp, ffmpeg, demucs (CPU), rapidfuzz, pytest.

**Spec:** `../../../PLAN.md` §1–§4 (product, demo, architecture, evidence) and `../../../RESEARCH-2026-10-10.md` (measured STT and voice results). This plan covers the core pipeline only. Deployment (Cloud Run Job + API, Firestore, Firebase web app) is the next plan and consumes this package unchanged.

## Global Constraints

- Languages in this phase: `ko`, `en`, `ja`, `zh-Hans`. The source language is detected; the targets are the other three. Other languages come later through the same code path.
- Models: text = `gemini-3.8-flash` (never 3.1-pro). TTS = `gemini-3.8-flash-tts`. STT = Chirp 3 (`chirp_3`, location `us`).
- Voice: stored replicated voice `voice_apnqm460dgb6` via the Gemini API (`generativelanguage.googleapis.com/v1beta/interactions`, Keychain `gemini_api_key`). Fallback preset voice: `Puck`.
- Never use Gemini's own timestamps for timing. Timing comes only from Chirp 3 word offsets (measured: Gemini drifts up to 42 s).
- Google auth: never use the Mac's Application Default Credentials (they are the Inzeum account). Locally, use `gcloud auth print-access-token --account jaeho.shin@viberick.com` with `quota_project_id="viberick"`. On Cloud Run, the service account (next plan).
- Fresh code only: everything in `viberick-dub/` is written from 2026-10-10 on. Ideas and measured constants from autodub (built 2026-10-08) may be reused; no files copied from anything older than 2026-09-01.
- All code, comments, docs and UI text in English (contest rule).
- No secrets, voice recordings or run outputs in the repo: `.gitignore` covers `runs/`, `voice/`, `*.wav`, `*.m4a`, `.env`.
- Dub only Jaeho's own videos with his own voice.

## Review Focus

1. **Gemini API TTS rate limit.** Memory says AI Studio TTS allows about 10 requests/min. A 15-min video × 3 languages ≈ 750 line calls would take over an hour. Expected: paragraph synthesis (≤5 lines per call) plus a global rate gate keeps a 15-min video under ~20 min. Pinned by Task 1's probe and Task 8's rate gate test.
2. **Empty or partial model output.** TTS sometimes returns no audio; translation sometimes drops an id. Expected: retry, never a silent gap. Pinned in Task 6 (missing ids) and Task 8 (no-audio retry).
3. **Line longer than its slot even after two rewrites.** Expected: speed up to at most 1.35×, then spill into the following silence, later lines pushed and catching up. Pinned in Task 9 (`decide_tempo`) and Task 11 (`place` drift).
4. **Source longer than 20 minutes.** Chirp 3 batch with word timestamps is capped at 20 min. Expected: chunk at silences ≤18 min and offset the times. Pinned in Task 4 (`chunk_bounds`).
5. **English-source video.** Expected: source detected as `en`, targets `ko/ja/zh-Hans`, Korean budget used. Pinned in Task 5 (`targets_for`) and Task 6 (budget table covers all four). (There is no Task 7: it was folded into Task 6.).

---

## File Structure

```
viberick-dub/
  pyproject.toml          deps + pytest config
  .gitignore
  README.md               what it is, how to run (English)
  dub/
    __init__.py
    config.py             paths, model ids, languages, voice id, key + token loading
    gem.py                Gemini text client (Vertex): retry, JSON calls, cost ledger
    events.py             append-only events.jsonl writer (agent log, later streamed to the UI)
    fetch.py              yt-dlp → source.wav (+ metadata)
    separate.py           demucs CPU → vocals.wav + bed.wav
    align.py              pure: map characters of one text onto another's timed characters
    stt.py                Chirp 3 batch (GCS) → words; chunking for >20 min
    proofread.py          Gemini listens + fixes text and line breaks → cues timed via align.py
    units.py              cues → dubbing units with time slots; source language detection
    brief.py              topic, speaker style, term rules
    translate.py          per-language translation to a character budget; shorten()
    voice.py              Gemini API TTS (replicated or preset voice) → trimmed WAV; rate gate
    para.py               paragraph synthesis, cut into lines with Chirp sync word times
    fit.py                pure tempo decision + ffmpeg stretch
    check.py              Gemini listens to a clip → verdict
    agent.py              per-line repair loop (accept / resynthesize / shorten / retranslate)
    mix.py                place clips on the timeline, mix with bed, −14 LUFS m4a
    subs.py               SRT writer
    pipeline.py           CLI orchestration with per-step caching
    review.py             runs/<id>/review.html: play original vs each dub, per-line table
  tests/
    test_align.py test_units.py test_translate.py test_fit.py test_mix.py
    test_subs.py test_stt.py test_voice.py test_agent.py
  runs/                   (gitignored) one folder per video
```

---

### Task 1: Project skeleton, config, and the TTS rate probe

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`, `dub/__init__.py`, `dub/config.py`, `tools/probe_tts_rate.py`

**Interfaces:**
- Produces: `config.ROOT`, `config.RUNS`, `config.LANGS: dict[str, str]` (code → English name), `config.TEXT_MODEL`, `config.TTS_MODEL`, `config.VOICE_ID`, `config.FALLBACK_VOICE`, `config.gemini_key() -> str`, `config.gcp_token() -> str`, `config.GCP_PROJECT = "viberick"`, `config.BUCKET = "viberick-dub-lab"`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "viberick-dub"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "google-genai>=2.29.0",
  "google-cloud-speech>=2.30",
  "google-cloud-storage>=2.18",
  "rapidfuzz>=3.9",
  "yt-dlp>=2026.9.1",
  "httpx>=0.27",
]

[dependency-groups]
dev = ["pytest>=8"]
sep = ["demucs>=4.0.1", "torch>=2.4", "torchaudio>=2.4", "soundfile>=0.12"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: calls Google APIs (costs money, needs credentials)"]
addopts = "-m 'not live'"
```

- [ ] **Step 2: Write `.gitignore`**

```
runs/
voice/
*.wav
*.m4a
*.mp3
.env
.venv/
__pycache__/
```

- [ ] **Step 3: Write `dub/config.py`**

```python
"""Paths, model ids, languages, and credentials. Never prints secrets."""
import os
import subprocess
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("DUB_RUNS", ROOT / "runs"))

TEXT_MODEL = os.environ.get("DUB_TEXT_MODEL", "gemini-3.8-flash")
TTS_MODEL = os.environ.get("DUB_TTS_MODEL", "gemini-3.8-flash-tts")
VOICE_ID = os.environ.get("DUB_VOICE_ID", "voice_apnqm460dgb6")   # Jaeho's replicated voice
FALLBACK_VOICE = "Puck"

GCP_PROJECT = "viberick"
GCP_ACCOUNT = "jaeho.shin@viberick.com"
BUCKET = os.environ.get("DUB_BUCKET", "viberick-dub-lab")
STT_LOCATION = "us"          # chirp_3 runs only in us / eu

LANGS = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh-Hans": "Chinese (Simplified)"}
CHIRP_CODES = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP", "zh-Hans": "cmn-Hans-CN"}


@cache
def gemini_key() -> str:
    if k := os.environ.get("GEMINI_API_KEY"):
        return k
    r = subprocess.run(["security", "find-generic-password", "-s", "gemini_api_key", "-w"],
                       capture_output=True, text=True)
    if not r.stdout.strip():
        raise RuntimeError("GEMINI_API_KEY not set and not in Keychain (gemini_api_key)")
    return r.stdout.strip()


def gcp_token() -> str:
    """Access token for the viberick account. Not cached: tokens expire after ~1 h."""
    if t := os.environ.get("GCP_TOKEN"):
        return t
    r = subprocess.run(["gcloud", "auth", "print-access-token", "--account", GCP_ACCOUNT],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()
```

- [ ] **Step 4: Write `tools/probe_tts_rate.py` and run it**

```python
"""How many replicated-voice TTS calls per minute does the Gemini API key allow? Fires 30 short
calls at 1/s, counts 429s, prints the sustained rate. Cost: ~30 short clips (< $0.01)."""
import json
import time
import urllib.error
import urllib.request

from dub import config

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def call(text: str) -> int:
    body = {"model": config.TTS_MODEL,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": config.VOICE_ID}]}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": config.gemini_key(),
                                          "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120).read()
        return 200
    except urllib.error.HTTPError as e:
        return e.code


codes, t0 = [], time.time()
for i in range(30):
    codes.append(call(f"Test line number {i}."))
    time.sleep(max(0, (i + 1) - (time.time() - t0)))
ok = codes.count(200)
print(json.dumps({"ok": ok, "429": codes.count(429), "other": [c for c in codes if c not in (200, 429)],
                  "seconds": round(time.time() - t0, 1)}))
```

Run: `cd viberick-dub && uv sync && uv run python -m tools.probe_tts_rate`
Expected: a JSON line. If `429` > 0 at 1 call/s, the limit is below 60/min. Record the number in README "Limits". **If the limit is ≤10/min, raise it now:** ask Jaeho to re-record the consent with the Vertex sentence ("저는 이 음성의 소유자이며, Google Cloud를 사용하여 제 음성의 합성 모델을 생성하는 데 동의했습니다.") and create the voice on Vertex, where TTS had no observed cap. Add `DUB_TTS_BACKEND=vertex` support in Task 8.

- [ ] **Step 5: README skeleton** with one-paragraph description, `uv sync`, the CLI command from Task 13, and a "Limits" section holding the probe result.

- [ ] **Step 6: Commit** (once the folder becomes a git repo; until then, skip commit steps)

```bash
git init && git add -A && git commit -m "Project skeleton, config, TTS rate probe"
```

---

### Task 2: Events log and Gemini text client

**Files:**
- Create: `dub/events.py`, `dub/gem.py`

**Interfaces:**
- Produces: `events.log(run_dir: Path, kind: str, **data) -> None` (appends `{"t": unix, "kind": kind, **data}` to `run_dir/events.jsonl`). `gem.json_call(prompt: str, schema: dict, parts: list | None = None, thinking: str = "low") -> dict`, `gem.text_call(prompt: str, parts: list | None = None, thinking: str = "low") -> str`, `gem.LEDGER`, `gem.cost() -> float`.

- [ ] **Step 1: Write `dub/events.py`**

```python
"""Append-only agent event log. The web UI (next plan) tails this file / mirrors it to Firestore."""
import json
import threading
import time
from pathlib import Path

_lock = threading.Lock()


def log(run_dir: Path, kind: str, **data) -> None:
    line = json.dumps({"t": round(time.time(), 3), "kind": kind, **data}, ensure_ascii=False)
    with _lock, open(run_dir / "events.jsonl", "a") as f:
        f.write(line + "\n")
```

- [ ] **Step 2: Write `dub/gem.py`**

```python
"""Gemini text calls on Vertex (project viberick credit) with retry, JSON mode and a cost ledger."""
import json
import random
import threading
import time

from google import genai
from google.genai import types

from . import config

# USD per 1M tokens (in, out). Estimates for the cost slide only.
PRICE = {config.TEXT_MODEL: (0.75, 3.75)}
LEDGER: dict[str, dict] = {}
_lock = threading.Lock()
_gate = threading.BoundedSemaphore(24)
_client = None


def client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, api_key=config.gemini_key())
    return _client


def _record(model: str, resp) -> None:
    u = getattr(resp, "usage_metadata", None)
    if not u:
        return
    with _lock:
        row = LEDGER.setdefault(model, {"calls": 0, "in": 0, "out": 0})
        row["calls"] += 1
        row["in"] += u.prompt_token_count or 0
        row["out"] += (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


def cost() -> float:
    return round(sum(r["in"] / 1e6 * PRICE.get(m, (1, 10))[0] + r["out"] / 1e6 * PRICE.get(m, (1, 10))[1]
                     for m, r in LEDGER.items()), 4)


def _call(contents, cfg: types.GenerateContentConfig, tries: int = 8):
    for i in range(tries):
        try:
            with _gate:
                resp = client().models.generate_content(model=config.TEXT_MODEL, contents=contents, config=cfg)
            _record(config.TEXT_MODEL, resp)
            return resp
        except Exception as e:  # noqa: BLE001  429/500 from the shared pool
            if i == tries - 1 or str(e).startswith("400"):
                raise
            time.sleep(min(60, 2 ** i) * (0.5 + random.random()))


def json_call(prompt: str, schema: dict, parts: list | None = None, thinking: str = "low") -> dict:
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return json.loads(_call([*(parts or []), prompt], cfg).text)


def text_call(prompt: str, parts: list | None = None, thinking: str = "low") -> str:
    cfg = types.GenerateContentConfig(max_output_tokens=65536,
                                      thinking_config=types.ThinkingConfig(thinking_level=thinking))
    return _call([*(parts or []), prompt], cfg).text
```

- [ ] **Step 3: Live smoke test** — `tests/test_gem.py`

```python
import pytest
from dub import gem


@pytest.mark.live
def test_json_call_roundtrip():
    out = gem.json_call("Return the number 7.", {"type": "object", "properties": {"n": {"type": "integer"}},
                                                  "required": ["n"]})
    assert out["n"] == 7
    assert gem.cost() > 0
```

Run: `uv run pytest -m live tests/test_gem.py -v` → PASS.

- [ ] **Step 4: Commit** — `git add dub/events.py dub/gem.py tests/test_gem.py && git commit -m "Event log and Gemini text client"`

---

### Task 3: Character alignment (pure)

**Files:**
- Create: `dub/align.py`, `tests/test_align.py`

**Interfaces:**
- Produces: `align.norm_chars(text: str) -> list[str]` (lowercase letters, digits, Hangul, kana, CJK ideographs; everything else dropped). `align.timed_chars(units: list[dict]) -> tuple[str, list[float]]` (units have `start`, `end`, `text`; times linearly interpolated within a unit). `align.retime(lines: list[str], words: list[dict]) -> list[dict]` (words have `w`, `start`, `end`; returns `[{"start", "end", "text"}]` per line, lines with no alignable character are merged into the previous cue).

- [ ] **Step 1: Write the failing tests**

```python
from dub import align

WORDS = [{"w": "안녕하세요", "start": 0.0, "end": 1.0}, {"w": "바이브릭", "start": 1.2, "end": 2.0},
         {"w": "입니다", "start": 2.1, "end": 2.6}]


def test_norm_keeps_hangul_kana_cjk_latin():
    assert "".join(align.norm_chars("Hi, 안녕! カナ 漢字 SEO-2")) == "hi안녕カナ漢字seo2"


def test_retime_maps_corrected_lines_to_word_times():
    cues = align.retime(["안녕하세요.", "바이브릭입니다."], WORDS)
    assert [c["text"] for c in cues] == ["안녕하세요.", "바이브릭입니다."]
    assert cues[0]["start"] == 0.0 and abs(cues[1]["start"] - 1.2) < 0.01
    assert abs(cues[1]["end"] - 2.6) < 0.2


def test_retime_survives_a_corrected_word():
    # STT heard "바이블릭"; the proofread text says "바이브릭"
    words = [dict(WORDS[0]), {"w": "바이블릭", "start": 1.2, "end": 2.0}, dict(WORDS[2])]
    cues = align.retime(["안녕하세요", "바이브릭입니다"], words)
    assert abs(cues[1]["start"] - 1.2) < 0.01


def test_line_without_letters_merges_into_previous():
    cues = align.retime(["안녕하세요", "...", "바이브릭입니다"], WORDS)
    assert len(cues) == 2 and cues[0]["text"].endswith("...")
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_align.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `dub/align.py`**

```python
"""Map one text's characters onto another's timed characters (Levenshtein alignment).

Used to give Gemini's corrected transcript the timing of Chirp 3's words: Chirp is accurate in time,
Gemini is accurate in text."""
import re

from rapidfuzz.distance import Levenshtein

_KEEP = re.compile(r"[0-9a-z가-힣぀-ヿ一-鿿]")


def norm_chars(text: str) -> list[str]:
    return [c for c in text.lower() if _KEEP.match(c)]


def timed_chars(units: list[dict]) -> tuple[str, list[float]]:
    chars, times = [], []
    for u in units:
        cs = norm_chars(u["text"])
        dur = max(0.0, (u["end"] or u["start"]) - u["start"])
        for i, c in enumerate(cs):
            chars.append(c)
            times.append(u["start"] + dur * i / max(1, len(cs)))
    return "".join(chars), times


def _map(a: str, b: str) -> dict[int, int]:
    m = {}
    for tag, sa, sb, da, db in Levenshtein.opcodes(a, b):
        if tag in ("equal", "replace"):
            for k in range(sa, sb):
                m[k] = da + min(k - sa, db - da - 1)
    return m


def retime(lines: list[str], words: list[dict]) -> list[dict]:
    ref, ref_t = timed_chars([{"start": w["start"], "end": w["end"], "text": w["w"]} for w in words])
    word_end = {}
    pos = 0
    for w in words:
        n = len(norm_chars(w["w"]))
        for k in range(pos, pos + n):
            word_end[k] = w["end"]
        pos += n
    owner, chars = [], []
    for li, line in enumerate(lines):
        for c in norm_chars(line):
            chars.append(c)
            owner.append(li)
    m = _map("".join(chars), ref)
    cues: list[dict] = []
    for li, line in enumerate(lines):
        idx = [k for k in range(len(chars)) if owner[k] == li and k in m]
        if not idx:
            if cues:
                cues[-1]["text"] = f"{cues[-1]['text']} {line}".strip()
            continue
        a, b = m[idx[0]], m[idx[-1]]
        cues.append({"start": round(ref_t[a], 3), "end": round(word_end.get(b, ref_t[b]), 3), "text": line})
    return cues
```

- [ ] **Step 4: Run tests** — `uv run pytest tests/test_align.py -v` → 4 PASS.
- [ ] **Step 5: Commit** — `git commit -am "Character alignment for retiming corrected text"` (after `git add`).

---

### Task 4: Fetch, separate, Chirp 3 transcription

**Files:**
- Create: `dub/fetch.py`, `dub/separate.py`, `dub/stt.py`, `tests/test_stt.py`

**Interfaces:**
- Consumes: `config.*`.
- Produces: `fetch.fetch(url: str, run_dir: Path) -> dict` (writes `source.mp4`, `source.wav` 48 kHz stereo, `source.stt.flac` 16 kHz mono; returns `{"id","title","channel","duration","description","tags"}` and writes `info.json`). `separate.separate(run_dir: Path) -> tuple[Path, Path]` (`vocals.wav`, `bed.wav`). `stt.chunk_bounds(duration: float, silences: list[tuple[float, float]], max_len: float = 1080.0) -> list[tuple[float, float]]`. `stt.chirp_words(audio: Path, lang: str, run_dir: Path) -> list[dict]` (`[{"w","start","end"}]`, absolute seconds). `stt.chirp_sync_words(wav_bytes: bytes, lang: str) -> list[dict]` (for clips < 60 s; used by para.py).

- [ ] **Step 1: Failing test for chunking (pure)**

```python
from dub import stt


def test_short_audio_is_one_chunk():
    assert stt.chunk_bounds(900.0, []) == [(0.0, 900.0)]


def test_long_audio_cuts_at_silence_before_limit():
    sil = [(500.0, 501.0), (1000.0, 1001.2), (1500.0, 1500.8)]
    b = stt.chunk_bounds(2000.0, sil, max_len=1080.0)
    assert b[0] == (0.0, 1000.6) and b[-1][1] == 2000.0
    assert all(e - s <= 1080.0 for s, e in b)


def test_long_audio_without_silence_hard_cuts():
    b = stt.chunk_bounds(2500.0, [], max_len=1080.0)
    assert b == [(0.0, 1080.0), (1080.0, 2160.0), (2160.0, 2500.0)]
```

- [ ] **Step 2: Run** `uv run pytest tests/test_stt.py -v` → FAIL.

- [ ] **Step 3: Implement `dub/fetch.py`**

```python
"""YouTube URL → source.mp4, source.wav (48 kHz stereo), source.stt.flac (16 kHz mono), info.json."""
import json
import os
import subprocess
from pathlib import Path


def video_id(url: str) -> str:
    out = subprocess.run(["yt-dlp", "--get-id", url], capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1]


def fetch(url: str, run_dir: Path) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    info_p = run_dir / "info.json"
    if info_p.exists() and (run_dir / "source.wav").exists():
        return json.loads(info_p.read_text())
    cmd = ["yt-dlp", "-f", "bv*[height<=1080]+ba/b", "--merge-output-format", "mp4",
           "-o", str(run_dir / "source.mp4"), "--write-info-json", "--no-playlist", url]
    if proxy := os.environ.get("DUB_PROXY"):
        cmd[1:1] = ["--proxy", proxy]
    subprocess.run(cmd, check=True)
    raw = json.loads((run_dir / "source.info.json").read_text())
    for args, name in ((["-ac", "2", "-ar", "48000"], "source.wav"),
                       (["-ac", "1", "-ar", "16000", "-c:a", "flac"], "source.stt.flac")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(run_dir / "source.mp4"), "-vn",
                        *args, str(run_dir / name)], check=True)
    info = {k: raw.get(k) for k in ("id", "title", "channel", "duration", "description", "tags")}
    info_p.write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info
```

- [ ] **Step 4: Implement `dub/separate.py`** (CPU demucs, cached)

```python
"""Voice / background split with demucs htdemucs on CPU. Output: vocals.wav, bed.wav (48 kHz)."""
import shutil
import subprocess
from pathlib import Path


def separate(run_dir: Path) -> tuple[Path, Path]:
    vocals, bed = run_dir / "vocals.wav", run_dir / "bed.wav"
    if vocals.exists() and bed.exists():
        return vocals, bed
    out = run_dir / "sep"
    subprocess.run(["uv", "run", "--group", "sep", "python", "-m", "demucs", "--two-stems", "vocals",
                    "-n", "htdemucs", "-d", "cpu", "-o", str(out), str(run_dir / "source.wav")], check=True)
    d = out / "htdemucs" / "source"
    shutil.move(d / "vocals.wav", vocals)
    shutil.move(d / "no_vocals.wav", bed)
    shutil.rmtree(out)
    return vocals, bed
```

- [ ] **Step 5: Implement `dub/stt.py`**

```python
"""Chirp 3 (Speech-to-Text v2, location us) → word timings.

Batch with word timestamps is capped at 20 min, so longer audio is cut at silences into ≤18-min
chunks and the times are offset back. Sync recognize (<60 s) is used to cut paragraph TTS takes."""
import re
import subprocess
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech as cs
from google.oauth2.credentials import Credentials

from . import config


def _creds() -> Credentials:
    return Credentials(config.gcp_token())


def _client() -> SpeechClient:
    return SpeechClient(credentials=_creds(), client_options=ClientOptions(
        api_endpoint=f"{config.STT_LOCATION}-speech.googleapis.com", quota_project_id=config.GCP_PROJECT))


def _cfg(lang: str) -> cs.RecognitionConfig:
    return cs.RecognitionConfig(auto_decoding_config=cs.AutoDetectDecodingConfig(),
                                language_codes=[config.CHIRP_CODES[lang]], model="chirp_3",
                                features=cs.RecognitionFeatures(enable_word_time_offsets=True,
                                                                enable_automatic_punctuation=True))


def chunk_bounds(duration: float, silences: list[tuple[float, float]],
                 max_len: float = 1080.0) -> list[tuple[float, float]]:
    bounds, start = [], 0.0
    while duration - start > max_len:
        cands = [(a + b) / 2 for a, b in silences if start + max_len * 0.5 < (a + b) / 2 <= start + max_len]
        cut = round(cands[-1], 3) if cands else start + max_len
        bounds.append((start, cut))
        start = cut
    bounds.append((start, duration))
    return bounds


def silences(audio: Path, noise_db: int = -35, min_sec: float = 0.6) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-i", str(audio), "-af", f"silencedetect=n={noise_db}dB:d={min_sec}",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def _duration(audio: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(audio)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _words(results, offset: float) -> list[dict]:
    out = []
    for r in results:
        if r.alternatives:
            for w in r.alternatives[0].words:
                out.append({"w": w.word, "start": round(offset + w.start_offset.total_seconds(), 3),
                            "end": round(offset + w.end_offset.total_seconds(), 3)})
    return out


def chirp_words(audio: Path, lang: str, run_dir: Path) -> list[dict]:
    bucket = storage.Client(project=config.GCP_PROJECT, credentials=_creds()).bucket(config.BUCKET)
    words: list[dict] = []
    for i, (a, b) in enumerate(chunk_bounds(_duration(audio), silences(audio))):
        part = run_dir / f"stt.part{i}.flac"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-to", str(b), "-i", str(audio),
                        "-c:a", "flac", str(part)], check=True)
        blob = bucket.blob(f"stt/{run_dir.name}/{part.name}")
        blob.upload_from_filename(part)
        uri = f"gs://{config.BUCKET}/{blob.name}"
        req = cs.BatchRecognizeRequest(
            recognizer=f"projects/{config.GCP_PROJECT}/locations/{config.STT_LOCATION}/recognizers/_",
            config=_cfg(lang), files=[cs.BatchRecognizeFileMetadata(uri=uri)],
            recognition_output_config=cs.RecognitionOutputConfig(inline_response_config=cs.InlineOutputConfig()))
        res = _client().batch_recognize(request=req).result(timeout=3600).results[uri]
        if res.error and res.error.code:
            raise RuntimeError(f"chirp_3 chunk {i}: {res.error.message}")
        words += _words(res.transcript.results, a)
        part.unlink()
    return words


def chirp_sync_words(wav_bytes: bytes, lang: str) -> list[dict]:
    req = cs.RecognizeRequest(
        recognizer=f"projects/{config.GCP_PROJECT}/locations/{config.STT_LOCATION}/recognizers/_",
        config=_cfg(lang), content=wav_bytes)
    return _words(_client().recognize(request=req).results, 0.0)
```

- [ ] **Step 6: Run unit tests** → 3 PASS. **Live check:** `uv run python -c "from dub import fetch,stt,config; from pathlib import Path; d=config.RUNS/'Fty2sz3dBwU'; fetch.fetch('https://youtu.be/Fty2sz3dBwU', d); w=stt.chirp_words(d/'source.stt.flac','ko',d); print(len(w), w[:3])"` → ~1700 words, first word near 0.0 s.
- [ ] **Step 7: Commit.**

---

### Task 5: Proofread, units, source language

**Files:**
- Create: `dub/proofread.py`, `dub/units.py`, `tests/test_units.py`

**Interfaces:**
- Consumes: `gem.text_call`, `align.retime`, `stt.chirp_words`.
- Produces: `proofread.proofread(audio: Path, words: list[dict], info: dict, lang: str) -> list[dict]` (cues `{"start","end","text"}`). `units.detect_language(text: str) -> str` (one of `config.LANGS`). `units.targets_for(src: str) -> list[str]`. `units.make_units(cues: list[dict], duration: float) -> list[dict]` (`{"id","start","end","slot","text"}`; slot = time until the next unit starts, capped at end + 0.8 s, min 0.6 s).

- [ ] **Step 1: Failing tests**

```python
from dub import units


def test_detect_language():
    assert units.detect_language("오늘은 SEO를 정리합니다") == "ko"
    assert units.detect_language("今日はSEOをまとめます") == "ja"
    assert units.detect_language("今天我们总结一下SEO") == "zh-Hans"
    assert units.detect_language("Today we cover SEO") == "en"


def test_targets_exclude_source():
    assert units.targets_for("ko") == ["en", "ja", "zh-Hans"]
    assert units.targets_for("en") == ["ko", "ja", "zh-Hans"]


def test_slots_extend_into_following_gap_but_not_forever():
    cues = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.2, "end": 3.0, "text": "b"},
            {"start": 9.0, "end": 10.0, "text": "c"}]
    u = units.make_units(cues, duration=12.0)
    assert [x["id"] for x in u] == [0, 1, 2]
    assert u[0]["slot"] == 2.2          # up to the next start
    assert u[1]["slot"] == 1.6          # capped at end + 0.8
    assert u[2]["slot"] == 1.8          # last: end + 0.8, within duration
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `dub/units.py`**

```python
"""Cues → dubbing units with time slots; crude script-based source language detection."""
import re

from . import config


def detect_language(text: str) -> str:
    counts = {"ko": len(re.findall(r"[가-힣]", text)), "ja": len(re.findall(r"[぀-ヿ]", text)),
              "zh-Hans": len(re.findall(r"[一-鿿]", text)), "en": len(re.findall(r"[A-Za-z]", text)) / 4}
    if counts["ja"] > 0:
        return "ja"   # kana only appears in Japanese
    return max(counts, key=counts.get)


def targets_for(src: str) -> list[str]:
    return [lang for lang in config.LANGS if lang != src]


def make_units(cues: list[dict], duration: float) -> list[dict]:
    out = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else duration
        slot = max(0.6, min(nxt, c["end"] + 0.8, duration) - c["start"])
        out.append({"id": i, "start": c["start"], "end": c["end"], "slot": round(slot, 3), "text": c["text"]})
    return out
```

- [ ] **Step 4: Implement `dub/proofread.py`**

```python
"""Gemini listens to the audio and corrects Chirp's transcript; line breaks at natural pauses.
Timing is NOT taken from Gemini: the corrected lines are re-timed onto Chirp's words (align.retime).
Measured on Fty2sz3dBwU: CER 7.6–7.9 % vs 8.6 % Chirp alone, timing p50 0.22 s, no drift."""
from pathlib import Path

from google.genai import types

from . import align, config, gem


def proofread(audio: Path, words: list[dict], info: dict, lang: str) -> list[dict]:
    draft = " ".join(w["w"] for w in words)
    prompt = (
        f"Below is a machine transcript of this {config.LANGS[lang]} YouTube video "
        f"(channel {info.get('channel')!r}; title {info.get('title')!r}; tags {info.get('tags') or []}).\n"
        "Listen to the audio and return the corrected transcript: fix misheard words, brand and tech terms "
        "(use the channel name, title and tags as ground truth for names), and spacing. Keep the speaker's "
        "actual words in order; do not paraphrase, summarize or drop anything. Put a line break at every "
        "natural pause: one subtitle-length phrase per line. Output only the transcript.\n\n" + draft)
    mime = "audio/flac" if audio.suffix == ".flac" else "audio/wav"
    text = gem.text_call(prompt, parts=[types.Part.from_bytes(data=audio.read_bytes(), mime_type=mime)])
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return align.retime(lines, words)
```

Note: inline audio limit is ~20 MB. 16 kHz mono FLAC is ~1.9 MB/min, so above ~10 min pass a GCS URI instead: `types.Part.from_uri(file_uri=gs_uri, mime_type="audio/flac")`, reusing the upload from Task 4 (store the GCS URIs in `stt.chirp_words` and proofread chunk by chunk with the same offsets).

- [ ] **Step 5: Run unit tests** → 3 PASS. **Live:** proofread the Fty2sz3dBwU words; check CER with the experiment script (`../experiments/2026-10-10-stt/score.py`, pointed at the new cues) is ≤8.5 %.
- [ ] **Step 6: Commit.**

---

### Task 6: Brief and time-budgeted translation

**Files:**
- Create: `dub/brief.py`, `dub/translate.py`, `tests/test_translate.py`

**Interfaces:**
- Consumes: `gem.json_call`, units from Task 5.
- Produces: `brief.make_brief(units: list[dict], info: dict, src: str) -> dict` (`{"summary","speaker_style","terms":[{"source","rule"}]}`). `translate.CPS: dict[str, float]`. `translate.budget(lang: str, seconds: float) -> int`. `translate.translate(units, src: str, lang: str, brief: dict) -> list[str]` (one string per unit, never empty for a non-empty source). `translate.shorten(src_text: str, text: str, lang: str, seconds: float, ratio: float) -> str`.

- [ ] **Step 1: Failing tests (pure parts, Gemini mocked)**

```python
from dub import translate


def test_budget_scales_with_language_rate():
    assert translate.budget("en", 2.0) > translate.budget("ja", 2.0) > 0
    assert translate.budget("zh-Hans", 0.1) == 4          # floor


def test_missing_ids_are_retried_one_by_one(monkeypatch):
    calls = []

    def fake_batch(batch, src, lang, brief, prev):
        calls.append([u["id"] for u in batch])
        return ["" if (u["id"] == 1 and len(batch) > 1) else f"t{u['id']}" for u in batch]

    monkeypatch.setattr(translate, "_batch", fake_batch)
    units = [{"id": i, "text": f"s{i}", "slot": 2.0} for i in range(3)]
    out = translate.translate(units, "ko", "en", {"summary": "", "terms": []})
    assert out == ["t0", "t1", "t2"] and calls[-1] == [1]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `dub/brief.py`**

```python
"""One pass over the whole transcript: topic, speaker style, and term rules for translators."""
from . import config, gem

SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string"}, "speaker_style": {"type": "string"},
    "terms": {"type": "array", "items": {"type": "object", "properties": {
        "source": {"type": "string"}, "rule": {"type": "string"}}, "required": ["source", "rule"]}}},
    "required": ["summary", "speaker_style", "terms"]}


def make_brief(units: list[dict], info: dict, src: str) -> dict:
    text = "\n".join(f"[{u['id']}] {u['text']}" for u in units)
    return gem.json_call(
        f"Video title: {info.get('title')}\nChannel: {info.get('channel')}\nTags: {info.get('tags') or []}\n"
        f"Transcript ({config.LANGS[src]}):\n{text}\n\n"
        "Prepare a dubbing brief. summary: 3 sentences on topic and audience. speaker_style: tone, energy "
        "and formality in one sentence. terms: product names, acronyms, jargon and proper nouns, each with a "
        "rule (keep as-is / translate as X / spell out). Use the channel name, title and tags as ground truth "
        "for brand spelling.", SCHEMA)
```

- [ ] **Step 4: Implement `dub/translate.py`**

```python
"""Dubbing translation: every line must be speakable inside its time slot.

CPS = characters per second of the TTS voice at natural speed. en/ja/zh-Hans/ko values were measured on
gemini-3.8-flash-tts preset voices (2026-10-08, 114–323 lines per language). Re-measure on the replicated
voice in Task 13 and update."""
from concurrent.futures import ThreadPoolExecutor

from . import config, gem

CPS = {"en": 15.1, "ja": 6.2, "zh-Hans": 5.2, "ko": 7.0}
BATCH = 40
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
    "required": ["id", "text"]}}}, "required": ["lines"]}


def budget(lang: str, seconds: float) -> int:
    return max(4, int(CPS.get(lang, 14.0) * seconds * 0.95))


def _batch(batch: list[dict], src: str, lang: str, brief: dict, prev: list[str]) -> list[str]:
    lines = "\n".join(f'{{"id":{u["id"]},"max_chars":{budget(lang, u["slot"])},"src":{u["text"]!r}}}'
                      for u in batch)
    terms = "\n".join(f"- {t['source']}: {t['rule']}" for t in brief.get("terms", []))
    out = gem.json_call(
        f"You are a professional dubbing translator. Translate each {config.LANGS[src]} line into "
        f"{config.LANGS[lang]} for a voice-over that replaces the original speech.\n"
        f"Topic: {brief.get('summary', '')}\nTerms:\n{terms}\n"
        f"Previous lines (continuity): {' '.join(prev[-3:]) or '(start)'}\n\nRules:\n"
        "- Use between 75% and 100% of max_chars (100% = the slot at natural speed). Under 75% leaves dead "
        "air while the speaker is visibly talking; over 100% will not fit.\n"
        "- Reach the length by translating fully, never by adding things the source does not say. If the "
        "meaning is longer than max_chars, cut redundancy and fillers first, never the point.\n"
        "- Drop spoken fillers and false starts unless they carry meaning. Keep the friendly, direct tone.\n"
        "- Consecutive lines may be fragments of one sentence; they must read naturally when joined.\n"
        "- Numbers, URLs and code as a speaker would say them.\n"
        "- Output every id exactly once, same order.\n\nLines:\n" + lines, SCHEMA)
    got = {l["id"]: l["text"].strip() for l in out["lines"]}
    return [got.get(u["id"], "") for u in batch]


def translate(units: list[dict], src: str, lang: str, brief: dict) -> list[str]:
    batches = [units[i:i + BATCH] for i in range(0, len(units), BATCH)]
    with ThreadPoolExecutor(max(1, len(batches))) as ex:
        parts = list(ex.map(lambda ib: _batch(ib[1], src, lang, brief,
                                              [u["text"] for u in batches[ib[0] - 1]] if ib[0] else []),
                            enumerate(batches)))
    out = [t for p in parts for t in p]
    for i, t in enumerate(out):
        if not t and units[i]["text"].strip():
            out[i] = _batch([units[i]], src, lang, brief, out[max(0, i - 3):i])[0]
    return out


def shorten(src_text: str, text: str, lang: str, seconds: float, ratio: float) -> str:
    target = max(4, int(len(text) * 0.93 / ratio))
    return gem.json_call(
        f"This {config.LANGS[lang]} dubbing line runs {ratio:.0%} of its {seconds:.1f}s slot. Rewrite it in at "
        f"most {target} characters. Keep the point of the original and the tone; drop redundancy, never "
        f"meaning.\nOriginal: {src_text}\nCurrent: {text}",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})["text"].strip()
```

- [ ] **Step 5: Run** → 2 PASS. **Commit.**

---

### Task 8: Voice synthesis with the cloned voice and a rate gate

**Files:**
- Create: `dub/voice.py`, `tests/test_voice.py`

**Interfaces:**
- Consumes: `config.VOICE_ID`, `config.gemini_key()`.
- Produces: `voice.RATE = 24000`. `voice.synth(text: str, out: Path, voice_id: str = config.VOICE_ID) -> float` (trimmed, faded 24 kHz mono WAV; returns seconds; retries no-audio responses). `voice.duration(p: Path) -> float`. `voice.pcm(p: Path) -> bytes`. `voice.RateGate(per_min: int)` with `.wait()`.

- [ ] **Step 1: Failing tests (network mocked)**

```python
import time
from dub import voice


def test_rate_gate_spaces_calls():
    g = voice.RateGate(per_min=120)       # 0.5 s apart
    t0 = time.time()
    for _ in range(3):
        g.wait()
    assert time.time() - t0 >= 0.95


def test_synth_retries_when_no_audio(monkeypatch, tmp_path):
    seq = [b"", voice._silence_wav(0.6)]
    monkeypatch.setattr(voice, "_request", lambda text, vid: seq.pop(0))
    monkeypatch.setattr(voice, "_trim_fade", lambda raw, out: out.write_bytes(raw) or 0.6)
    assert voice.synth("hello", tmp_path / "a.wav") == 0.6
    assert seq == []
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `dub/voice.py`**

```python
"""gemini-3.8-flash-tts through the Gemini API with a stored replicated voice → trimmed 24 kHz WAV.

Send the bare line only: the model reads style instructions aloud (measured 2026-10-08)."""
import base64
import io
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

from . import config

RATE = 24000
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class RateGate:
    def __init__(self, per_min: int):
        self.gap = 60.0 / per_min
        self.next = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.time()
            t = max(now, self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - now))


GATE = RateGate(int(os.environ.get("DUB_TTS_PER_MIN", "60")))   # set from the Task 1 probe


def _find_audio(x) -> str | None:
    if isinstance(x, dict):
        if isinstance(x.get("data"), str) and len(x["data"]) > 1000:
            return x["data"]
        x = list(x.values())
    if isinstance(x, list):
        for v in x:
            if (d := _find_audio(v)):
                return d
    return None


def _request(text: str, voice_id: str) -> bytes:
    body = {"model": config.TTS_MODEL,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice_id}]}}
    for i in range(8):
        GATE.wait()
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"x-goog-api-key": config.gemini_key(),
                                              "Content-Type": "application/json"})
        try:
            data = _find_audio(json.load(urllib.request.urlopen(req, timeout=180)))
            return base64.b64decode(data) if data else b""
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or i == 7:
                raise RuntimeError(f"TTS {e.code}: {e.read().decode()[:300]}") from e
            time.sleep(min(60, 2 ** i))
    return b""


def _silence_wav(sec: float) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(b"\x00\x00" * int(RATE * sec))
    return b.getvalue()


def duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def pcm(p: Path) -> bytes:
    with wave.open(str(p)) as w:
        return w.readframes(w.getnframes())


def _trim_fade(raw: bytes, out: Path) -> float:
    tmp = out.with_suffix(".raw.wav")
    tmp.write_bytes(raw)
    flt = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
           "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
           f"aresample={RATE},afade=t=in:d=0.012")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-ac", "1", "-af", flt, str(out)],
                   check=True)
    tmp.unlink()
    return duration(out)


def synth(text: str, out: Path, voice_id: str = config.VOICE_ID) -> float:
    for _ in range(4):
        raw = _request(text, voice_id)
        if len(raw) > RATE // 5:
            return _trim_fade(raw, out)
    raise RuntimeError(f"TTS returned no audio for {text[:40]!r}")
```

- [ ] **Step 4: Run** → 2 PASS. **Live:** `uv run python -c "from dub import voice; from pathlib import Path; print(voice.synth('Hello from VibeRick Dub.', Path('/tmp/v.wav')))"` → ~1.5 s, sounds like Jaeho.
- [ ] **Step 5: Commit.**

---

### Task 9: Fit decisions (pure) and stretch

**Files:**
- Create: `dub/fit.py`, `tests/test_fit.py`

**Interfaces:**
- Produces: `fit.MAX_TEMPO = 1.25`, `fit.HARD_MAX = 1.35`, `fit.MIN_TEMPO = 0.92`. `fit.needs_shorter(dur: float, slot: float) -> bool`. `fit.decide_tempo(dur: float, slot: float) -> float`. `fit.stretch(src: Path, dst: Path, tempo: float) -> float`.

- [ ] **Step 1: Failing tests**

```python
from dub import fit


def test_fits_untouched():
    assert fit.decide_tempo(1.9, 2.0) == 1.0


def test_overrun_speeds_up_but_capped():
    assert abs(fit.decide_tempo(2.2, 2.0) - 1.1) < 1e-6
    assert fit.decide_tempo(4.0, 2.0) == fit.HARD_MAX


def test_short_line_eased_toward_slot_not_below_floor():
    assert fit.decide_tempo(1.0, 2.0) == fit.MIN_TEMPO


def test_needs_shorter_only_past_max_tempo():
    assert not fit.needs_shorter(2.4, 2.0) and fit.needs_shorter(2.6, 2.0)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

```python
"""Tempo decisions for one dubbed line (ratio = spoken seconds / slot seconds)."""
import subprocess
from pathlib import Path

from . import voice

MAX_TEMPO = 1.25     # above this, ask for a shorter line first
HARD_MAX = 1.35      # never speed up more than this
MIN_TEMPO = 0.92     # slow very short lines slightly, never more


def needs_shorter(dur: float, slot: float) -> bool:
    return dur / slot > MAX_TEMPO


def decide_tempo(dur: float, slot: float) -> float:
    r = dur / slot
    if r > 1.0:
        return min(r, HARD_MAX)
    return max(MIN_TEMPO, min(1.0, r / 0.8))


def stretch(src: Path, dst: Path, tempo: float) -> float:
    if abs(tempo - 1.0) < 0.01:
        dst.write_bytes(src.read_bytes())
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                        f"atempo={tempo:.4f}", str(dst)], check=True)
    return voice.duration(dst)
```

- [ ] **Step 4: Run** → 4 PASS. **Commit.**

---

### Task 10: Paragraph synthesis cut by Chirp word times

**Files:**
- Create: `dub/para.py`, `tests/test_para.py`

**Interfaces:**
- Consumes: `voice.synth`, `stt.chirp_sync_words`, `align.retime`.
- Produces: `para.groups(units: list[dict], max_lines: int = 5, max_gap: float = 1.5, max_sec: float = 32.0) -> list[list[int]]` (indices). `para.cut_points(lines: list[str], words: list[dict]) -> list[float] | None` (start time of each line inside the take; None if alignment fails). `para.synth_group(lines: list[str], lang: str, d: Path, ids: list[int]) -> bool` (writes `<id>.tts.wav` for every id; False → caller falls back to per-line).

Why: one TTS call per ≤5 lines cuts calls ~4× (Review Focus 1) and keeps one consistent read across a paragraph (autodub: per-line calls sounded like "voice switching").

- [ ] **Step 1: Failing tests**

```python
from dub import para


def test_groups_break_on_long_pause_and_size():
    u = [{"start": s, "end": s + 1.0, "slot": 1.2} for s in (0, 1.2, 2.4, 6.0, 7.2, 8.4, 9.6, 10.8, 12.0)]
    g = para.groups(u, max_lines=5, max_gap=1.5)
    assert g == [[0, 1, 2], [3, 4, 5, 6, 7], [8]]


def test_cut_points_from_words():
    words = [{"w": "Hello", "start": 0.1, "end": 0.5}, {"w": "there.", "start": 0.55, "end": 0.9},
             {"w": "How", "start": 1.3, "end": 1.5}, {"w": "are", "start": 1.55, "end": 1.7},
             {"w": "you?", "start": 1.75, "end": 2.0}]
    assert para.cut_points(["Hello there.", "How are you?"], words) == [0.0, 1.1]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

```python
"""Synthesize ≤5 consecutive lines in one take, then cut it back into lines.

Cut points: Chirp 3 sync recognition on the take → word times → align each line's first character →
cut midway between the previous line's last word and this line's first word."""
import subprocess
from pathlib import Path

from . import align, stt, voice


def groups(units: list[dict], max_lines: int = 5, max_gap: float = 1.5, max_sec: float = 32.0) -> list[list[int]]:
    out, cur = [], []
    for i, u in enumerate(units):
        if cur:
            gap = u["start"] - units[cur[-1]]["end"]
            span = u["end"] - units[cur[0]]["start"]
            if gap > max_gap or len(cur) >= max_lines or span > max_sec:
                out.append(cur)
                cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def cut_points(lines: list[str], words: list[dict]) -> list[float] | None:
    cues = align.retime(lines, words)
    if len(cues) != len(lines):
        return None
    pts = [0.0]
    for prev, cur in zip(cues, cues[1:]):
        pts.append(round((prev["end"] + cur["start"]) / 2, 3))
    return pts


def synth_group(lines: list[str], lang: str, d: Path, ids: list[int]) -> bool:
    take = d / f"take_{ids[0]:04d}.wav"
    voice.synth(" ".join(lines), take)
    if len(lines) == 1:
        take.replace(d / f"{ids[0]:04d}.tts.wav")
        return True
    pts = cut_points(lines, stt.chirp_sync_words(take.read_bytes(), lang))
    if pts is None:
        return False
    end = voice.duration(take)
    for k, i in enumerate(ids):
        a, b = pts[k], (pts[k + 1] if k + 1 < len(pts) else end)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(take), "-ss", f"{a:.3f}", "-to",
                        f"{b:.3f}", "-af", "afade=t=in:d=0.012", str(d / f"{i:04d}.tts.wav")], check=True)
    take.unlink()
    return True
```

- [ ] **Step 4: Run** → 2 PASS. **Commit.**

---

### Task 11: Placement and mix

**Files:**
- Create: `dub/mix.py`, `tests/test_mix.py`

**Interfaces:**
- Produces: `mix.place(units: list[dict], clips: list[Path], total: float, out: Path) -> dict` (`{"late_max","late_p95","late_lines"}`; writes 24 kHz mono timeline; a clip starts at `max(unit.start, previous clip end + 0.08)`). `mix.mix(voice_wav: Path, bed: Path | None, out: Path) -> None` (48 kHz stereo AAC 160k, −14 LUFS).

- [ ] **Step 1: Failing test (synthetic clips)**

```python
from dub import mix, voice


def test_overlong_clip_pushes_next_and_catches_up(tmp_path):
    clips = []
    for i, sec in enumerate([1.5, 0.5, 0.5]):
        p = tmp_path / f"{i}.wav"
        p.write_bytes(voice._silence_wav(sec))
        clips.append(p)
    units = [{"start": 0.0}, {"start": 1.0}, {"start": 3.0}]
    st = mix.place(units, clips, total=4.0, out=tmp_path / "t.wav")
    assert abs(st["late_max"] - 0.58) < 0.01 and st["late_lines"] == 1
    assert abs(voice.duration(tmp_path / "t.wav") - 5.0) < 0.01   # total + 1 s tail
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

```python
"""Lay dubbed clips on the original timeline, then mix with the background bed."""
import subprocess
import wave
from pathlib import Path

from . import voice


def place(units: list[dict], clips: list[Path], total: float, out: Path) -> dict:
    rate = voice.RATE
    buf = bytearray((int(total * rate) + rate) * 2)
    cursor, late = 0.0, []
    for u, c in zip(units, clips):
        start = max(u["start"], cursor)
        late.append(start - u["start"])
        pcm = voice.pcm(c)
        a = int(start * rate) * 2
        b = min(len(buf), a + len(pcm))
        buf[a:b] = pcm[: b - a]
        cursor = start + len(pcm) / 2 / rate + 0.08
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(bytes(buf))
    s = sorted(late)
    return {"late_max": round(s[-1], 2), "late_p95": round(s[int(len(s) * 0.95)], 2),
            "late_lines": sum(1 for x in late if x > 0.3)}


def mix(voice_wav: Path, bed: Path | None, out: Path) -> None:
    if bed:
        fc = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];[1:a]aresample=48000[b];"
              "[v][b]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11")
        cmd = ["-i", str(voice_wav), "-i", str(bed), "-filter_complex", fc]
    else:
        cmd = ["-i", str(voice_wav), "-af", "aresample=48000,pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1.5:LRA=11"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *cmd, "-c:a", "aac", "-b:a", "160k", str(out)],
                   check=True)
```

- [ ] **Step 4: Run** → PASS. **Commit.**

---

### Task 12: Check and the repair agent

**Files:**
- Create: `dub/check.py`, `dub/agent.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `voice.synth`, `fit.*`, `translate.shorten`, `translate._batch` (retranslate one line), `events.log`.
- Produces: `check.check(clip: Path, text: str, lang: str) -> dict` (`{"heard","language_ok","content_ok","issue"}`). `agent.repair_line(u: dict, text: str, src: str, lang: str, brief: dict, d: Path, run_dir: Path, pre: bool) -> dict` (row `{"id","text","dur","slot","tempo","actions":[...],"ok","issue","heard"}`; writes `<id>.wav`). `agent.MAX_STEPS = 4`.

Agent policy (deterministic loop, Gemini decides content; every action logged as an event):
1. synthesize (unless `pre`) → measure.
2. if `fit.needs_shorter` → `shorten` (≤2 times), resynthesize.
3. stretch with `fit.decide_tempo`.
4. `check`: language_ok and content_ok → accept.
5. else: first failure → resynthesize same text; second failure → retranslate this line then resynthesize; then accept with `ok=False` and the issue (shown in the review UI for a human).

- [ ] **Step 1: Failing test (all model calls mocked)**

```python
from dub import agent


def test_agent_shortens_then_retries_then_accepts(monkeypatch, tmp_path):
    durs = iter([3.0, 2.2, 2.2])                 # too long → shorter → resynth after failed check
    monkeypatch.setattr(agent.voice, "synth", lambda text, out, **k: (out.write_bytes(b"x"), next(durs))[1])
    monkeypatch.setattr(agent.translate, "shorten", lambda *a: "short")
    monkeypatch.setattr(agent.fit, "stretch", lambda s, d, t: d.write_bytes(b"x") or 2.0)
    verdicts = iter([{"heard": "", "language_ok": True, "content_ok": False, "issue": "garbled"},
                     {"heard": "short", "language_ok": True, "content_ok": True, "issue": ""}])
    monkeypatch.setattr(agent.check, "check", lambda *a: next(verdicts))
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    u = {"id": 0, "text": "원문", "slot": 2.0}
    row = agent.repair_line(u, "a long line", "ko", "en", {}, tmp_path, tmp_path, pre=False)
    assert row["ok"] and row["text"] == "short"
    assert [a["do"] for a in row["actions"]] == ["synth", "shorten", "synth", "check", "resynth", "check"]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `dub/check.py`**

```python
"""Gemini listens to one dubbed clip and says whether it is the right line in the right language."""
from pathlib import Path

from google.genai import types

from . import config, gem

SCHEMA = {"type": "object", "properties": {"heard": {"type": "string"}, "language_ok": {"type": "boolean"},
                                           "content_ok": {"type": "boolean"}, "issue": {"type": "string"}},
          "required": ["heard", "language_ok", "content_ok", "issue"]}


def check(clip: Path, text: str, lang: str) -> dict:
    return gem.json_call(
        f"Listen to this dubbing clip. Expected language: {config.LANGS[lang]}. Expected line: {text!r}\n"
        "heard: what is actually said. language_ok: spoken in the expected language. content_ok: says the "
        "expected line (contractions, number formats and punctuation are fine; extra words or sounds, spoken "
        "instructions, missing clauses, garbled or truncated speech are not). issue: '' if fine.",
        SCHEMA, parts=[types.Part.from_bytes(data=clip.read_bytes(), mime_type="audio/wav")])
```

- [ ] **Step 4: Implement `dub/agent.py`**

```python
"""Per-line repair loop: measure → shorten → stretch → listen → resynthesize / retranslate → accept.

Every action is logged to events.jsonl; the web UI replays it as the agent's live work log."""
from pathlib import Path

from . import check, events, fit, translate, voice

MAX_STEPS = 4


def repair_line(u: dict, text: str, src: str, lang: str, brief: dict, d: Path, run_dir: Path,
                pre: bool) -> dict:
    raw, out = d / f"{u['id']:04d}.tts.wav", d / f"{u['id']:04d}.wav"
    acts: list[dict] = []

    def act(do: str, **kw):
        acts.append({"do": do, **kw})
        events.log(run_dir, "line", lang=lang, id=u["id"], do=do, **kw)

    dur = voice.duration(raw) if pre else voice.synth(text, raw)
    act("synth", dur=round(dur, 2), slot=u["slot"], pre=pre)
    for _ in range(2):
        if not fit.needs_shorter(dur, u["slot"]):
            break
        text = translate.shorten(u["text"], text, lang, u["slot"], dur / u["slot"])
        act("shorten", text=text)
        dur = voice.synth(text, raw)
        act("synth", dur=round(dur, 2), slot=u["slot"])
    v = {"heard": "", "issue": ""}
    for attempt in range(MAX_STEPS):
        tempo = fit.decide_tempo(dur, u["slot"])
        final = fit.stretch(raw, out, tempo)
        v = check.check(out, text, lang)
        act("check", ok=v["language_ok"] and v["content_ok"], issue=v["issue"])
        if v["language_ok"] and v["content_ok"]:
            return {"id": u["id"], "text": text, "dur": round(final, 3), "slot": u["slot"],
                    "tempo": round(tempo, 3), "actions": acts, "ok": True, "issue": "", "heard": v["heard"]}
        if attempt == 0:
            act("resynth")
        elif attempt == 1:
            text = translate._batch([u], src, lang, brief, [])[0] or text
            act("retranslate", text=text)
        else:
            break
        dur = voice.synth(text, raw)
    return {"id": u["id"], "text": text, "dur": round(voice.duration(out), 3), "slot": u["slot"],
            "tempo": round(fit.decide_tempo(dur, u["slot"]), 3), "actions": acts, "ok": False,
            "issue": v["issue"], "heard": v["heard"]}
```

- [ ] **Step 5: Run** → PASS. **Commit.**

---

### Task 13: Subtitles, pipeline CLI, review page — first end-to-end run

**Files:**
- Create: `dub/subs.py`, `dub/pipeline.py`, `dub/review.py`, `tests/test_subs.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `subs.srt(units: list[dict], texts: list[str], lang: str) -> str`. CLI: `uv run python -m dub.pipeline <url> [--to en,ja,zh-Hans] [--max-sec 180]` writing `runs/<id>/out/{dub.<lang>.m4a, subs.<lang>.srt, subs.<src>.srt, report.json}` and `runs/<id>/review.html`.

- [ ] **Step 1: Failing SRT test**

```python
from dub import subs


def test_srt_splits_long_cjk_line_and_keeps_timing():
    out = subs.srt([{"start": 1.0, "end": 5.0}], ["这是一个非常非常长的中文字幕行，需要被拆分成两行来显示，才能让观众看清楚"], "zh-Hans")
    blocks = [b for b in out.strip().split("\n\n") if b]
    assert len(blocks) == 2
    assert blocks[0].splitlines()[1].startswith("00:00:01,000 --> ")
    assert blocks[-1].splitlines()[1].endswith("00:00:05,000")
```

- [ ] **Step 2: Implement `dub/subs.py`**

```python
"""SRT writer: long lines split at punctuation into readable cues, timed by character share."""
import re

CJK = {"ja", "zh-Hans"}


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces = [p for p in re.split(r"(?<=[.!?。！？,，、;:])\s*", text) if p]
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip() if cur and not re.match(r"[぀-鿿]", p) else cur + p
    out.append(cur)
    final = []
    for c in out:
        while len(c) > limit * 1.3:
            cut = c.rfind(" ", 0, limit) if " " in c[:limit] else limit
            final.append(c[:cut].strip())
            c = c[cut:].strip()
        final.append(c)
    return [f for f in final if f]


def srt(units: list[dict], texts: list[str], lang: str) -> str:
    limit = 22 if lang in CJK else 42
    blocks, n = [], 1
    for u, t in zip(units, texts):
        parts = _split(t.strip(), limit)
        total = sum(len(p) for p in parts) or 1
        s = u["start"]
        for p in parts:
            e = s + (u["end"] - u["start"]) * len(p) / total
            blocks.append(f"{n}\n{_ts(s)} --> {_ts(e)}\n{p}\n")
            n += 1
            s = e
    return "\n".join(blocks)
```

- [ ] **Step 3: Implement `dub/pipeline.py`**

```python
"""URL → dubbed tracks + subtitles. Each step caches its artifact in runs/<id>/; delete it to redo.

uv run python -m dub.pipeline https://youtu.be/<id> --to en,ja,zh-Hans --max-sec 180"""
import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import (agent, brief as briefmod, config, events, fetch, gem, mix, para, proofread, review,
               separate, stt, subs, translate, units as unitsmod)


def _cached(p: Path, make):
    if p.exists():
        return json.loads(p.read_text())
    v = make()
    p.write_text(json.dumps(v, ensure_ascii=False, indent=1))
    return v


def dub_language(run_dir: Path, us: list[dict], src: str, lang: str, brf: dict, total: float, bed: Path) -> dict:
    t0 = time.time()
    d = run_dir / "dub" / lang
    d.mkdir(parents=True, exist_ok=True)
    texts = _cached(d / "texts.json", lambda: translate.translate(us, src, lang, brf))
    events.log(run_dir, "translated", lang=lang, lines=len(texts))
    pre = [False] * len(us)
    with ThreadPoolExecutor(8) as ex:
        for g, ok in ex.map(lambda g: (g, _safe_group(g, us, texts, lang, d)), para.groups(us)):
            for i in g:
                pre[i] = ok
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(lambda i: agent.repair_line(us[i], texts[i], src, lang, brf, d, run_dir, pre[i]),
                           range(len(us))))
    timeline = run_dir / "dub" / f"{lang}.voice.wav"
    drift = mix.place(us, [d / f"{r['id']:04d}.wav" for r in rows], total, timeline)
    out = run_dir / "out"
    out.mkdir(exist_ok=True)
    mix.mix(timeline, bed, out / f"dub.{lang}.m4a")
    (out / f"subs.{lang}.srt").write_text(subs.srt(us, [r["text"] for r in rows], lang))
    rep = {"lang": lang, "lines": len(rows), "ok": sum(r["ok"] for r in rows),
           "first_pass_ok": sum(1 for r in rows if [a["do"] for a in r["actions"]].count("check") == 1 and r["ok"]),
           "shortened": sum(1 for r in rows if any(a["do"] == "shorten" for a in r["actions"])),
           "para_lines": sum(pre), "sec": round(time.time() - t0, 1), **drift}
    (d.parent / f"{lang}.json").write_text(json.dumps({"report": rep, "rows": rows}, ensure_ascii=False, indent=1))
    events.log(run_dir, "language_done", **rep)
    return rep


def _safe_group(g, us, texts, lang, d) -> bool:
    try:
        return para.synth_group([texts[i] for i in g], lang, d, [us[i]["id"] for i in g])
    except Exception:  # noqa: BLE001  per-line synthesis in the agent is the fallback
        return False


def main(url: str, to: list[str] | None, max_sec: float | None) -> Path:
    t0 = time.time()
    vid = fetch.video_id(url)
    run_dir = config.RUNS / vid
    run_dir.mkdir(parents=True, exist_ok=True)
    events.log(run_dir, "start", url=url)
    info = fetch.fetch(url, run_dir)
    if max_sec:   # dev mode: first N seconds only
        for name in ("source.wav", "source.stt.flac"):
            p = run_dir / name
            cut = run_dir / f"cut.{name}"
            if not cut.exists():
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-t", str(max_sec), str(cut)], check=True)
        audio, wav = run_dir / "cut.source.stt.flac", run_dir / "cut.source.wav"
        total = min(max_sec, info["duration"])
    else:
        audio, wav, total = run_dir / "source.stt.flac", run_dir / "source.wav", info["duration"]
    vocals, bed = separate.separate(run_dir) if not max_sec else (None, None)
    if max_sec:
        bed = None   # skip demucs in dev mode; mix voice only
    src_guess = unitsmod.detect_language(f"{info.get('title', '')} {info.get('description', '')}")
    words = _cached(run_dir / "words.json", lambda: stt.chirp_words(audio, src_guess, run_dir))
    events.log(run_dir, "transcribed", words=len(words))
    cues = _cached(run_dir / "cues.json", lambda: proofread.proofread(audio, words, info, src_guess))
    src = unitsmod.detect_language(" ".join(c["text"] for c in cues))
    us = unitsmod.make_units(cues, total)
    (run_dir / "out").mkdir(exist_ok=True)
    (run_dir / "out" / f"subs.{src}.srt").write_text(subs.srt(us, [u["text"] for u in us], src))
    brf = _cached(run_dir / "brief.json", lambda: briefmod.make_brief(us, info, src))
    langs = to or unitsmod.targets_for(src)
    reports = [dub_language(run_dir, us, src, lang, brf, total, bed) for lang in langs]
    summary = {"video": vid, "src": src, "units": len(us), "langs": reports,
               "gemini_text_usd": gem.cost(), "sec_total": round(time.time() - t0, 1)}
    (run_dir / "out" / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    review.write(run_dir, wav, us, langs)
    events.log(run_dir, "done", **{k: summary[k] for k in ("units", "sec_total")})
    return run_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--to", default="")
    ap.add_argument("--max-sec", type=float, default=0)
    a = ap.parse_args()
    print(main(a.url, [x for x in a.to.split(",") if x] or None, a.max_sec or None))
```

- [ ] **Step 4: Implement `dub/review.py`** — a single static HTML file (no design effort, per Jaeho's preference for plain local review pages): one `<audio>` for the original and one per language, then a table per language (id, time, source text, dubbed text, tempo, ok, issue, actions). Paths relative to `runs/<id>/`.

```python
"""runs/<id>/review.html: listen to the original and each dub; inspect every line the agent touched."""
import html
import json
from pathlib import Path


def write(run_dir: Path, wav: Path, units: list[dict], langs: list[str]) -> Path:
    parts = [f"<h1>{html.escape(run_dir.name)}</h1><p>Original</p><audio controls src='{wav.name}'></audio>"]
    for lang in langs:
        data = json.loads((run_dir / "dub" / f"{lang}.json").read_text())
        rep = data["report"]
        parts.append(f"<h2>{lang}: {rep['ok']}/{rep['lines']} ok</h2>"
                     f"<audio controls src='out/dub.{lang}.m4a'></audio><table border=1 cellpadding=4>"
                     "<tr><th>#</th><th>t</th><th>source</th><th>dub</th><th>tempo</th><th>ok</th><th>actions</th></tr>")
        for u, r in zip(units, data["rows"]):
            acts = " → ".join(a["do"] for a in r["actions"])
            parts.append(f"<tr><td>{u['id']}</td><td>{u['start']:.1f}</td><td>{html.escape(u['text'])}</td>"
                         f"<td>{html.escape(r['text'])}</td><td>{r['tempo']}</td>"
                         f"<td>{'✓' if r['ok'] else '✗ ' + html.escape(r['issue'])}</td><td>{acts}</td></tr>")
        parts.append("</table>")
    p = run_dir / "review.html"
    p.write_text("<meta charset=utf-8><body style='font:14px system-ui;max-width:1100px;margin:auto'>" + "".join(parts))
    return p
```

- [ ] **Step 5: Unit tests** — `uv run pytest -v` → all PASS.

- [ ] **Step 6: First end-to-end dev run (3 minutes, voice only)**

Run: `uv run python -m dub.pipeline https://youtu.be/Fty2sz3dBwU --max-sec 180`
Expected: `runs/Fty2sz3dBwU/out/dub.en.m4a`, `dub.ja.m4a`, `dub.zh-Hans.m4a`, four SRTs, `report.json`, `review.html`. In `report.json`: `ok/lines ≥ 0.9` per language, `late_max < 2.0`. Open `review.html` and listen to the English track. **Jaeho reviews by ear before the full run.**

- [ ] **Step 7: Full run (15 min, with demucs bed)**

Run: `uv run python -m dub.pipeline https://youtu.be/Fty2sz3dBwU`
Record in README: wall time, `gemini_text_usd`, TTS call count, ok ratios, `late_p95` per language.

- [ ] **Step 8: Re-measure CPS on the replicated voice** from `runs/Fty2sz3dBwU/dub/<lang>.json` rows (`len(text) / dur` at tempo 1.0, median) and update `translate.CPS`. Commit.

---

## Out of scope for this plan (next plan: deploy)

Cloud Run Job + API service, Firestore job/line documents mirrored from `events.jsonl`, Firebase Hosting web app (URL input, live agent log, per-language players, single-line regenerate, Studio kit zip), 100+ subtitle languages (translate SRT text only, no TTS), YouTube auto-dub comparison harness, budget caps.
