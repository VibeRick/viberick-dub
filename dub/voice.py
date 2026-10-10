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
CALLS = {"n": 0}


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


# Tier 3 key: 60/60 ok at 120/min (probe 2026-10-10). Tier 1 keys need 10.
GATE = RateGate(int(os.environ.get("DUB_TTS_PER_MIN", "240")))


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
        CALLS["n"] += 1
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"x-goog-api-key": config.tts_key(),
                                              "Content-Type": "application/json"})
        try:
            data = _find_audio(json.load(urllib.request.urlopen(req, timeout=180)))
            return base64.b64decode(data) if data else b""
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or i == 7:
                raise RuntimeError(f"TTS {e.code}: {e.read().decode()[:300]}") from e
            time.sleep(min(60, 2 ** i))
        except (urllib.error.URLError, TimeoutError):
            if i == 7:
                raise
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
    tmp = out.with_suffix(".raw.bin")
    tmp.write_bytes(raw)
    fmt = [] if raw[:4] == b"RIFF" else ["-f", "s16le", "-ar", str(RATE), "-ac", "1"]   # API returns raw PCM
    flt = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
           "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
           f"aresample={RATE},afade=t=in:d=0.012")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *fmt, "-i", str(tmp), "-ac", "1", "-af", flt,
                    "-c:a", "pcm_s16le", str(out)], check=True)
    tmp.unlink()
    return duration(out)


def synth(text: str, out: Path, voice_id: str = config.VOICE_ID) -> float:
    for _ in range(4):
        raw = _request(text, voice_id)
        if len(raw) > RATE // 5:
            return _trim_fade(raw, out)
    raise RuntimeError(f"TTS returned no audio for {text[:40]!r}")
