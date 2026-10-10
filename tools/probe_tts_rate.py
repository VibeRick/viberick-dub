"""How many replicated-voice TTS calls per minute does the Gemini API key allow? Fires 30 short
calls at 1/s, counts 429s, prints the sustained rate. Cost: ~30 short clips (< $0.01)."""
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from dub import config

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def call(text: str) -> int:
    body = {"model": config.TTS_MODEL,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": config.VOICE_ID}]}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": config.tts_key(),
                                          "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120).read()
        return 200
    except urllib.error.HTTPError as e:
        return e.code


t0 = time.time()
with ThreadPoolExecutor(60) as ex:
    futs = []
    for i in range(60):
        futs.append(ex.submit(call, f"Test line number {i}."))
        time.sleep(max(0, ((i + 1) / 2) - (time.time() - t0)))
    codes = [f.result() for f in futs]
print(json.dumps({"ok": codes.count(200), "429": codes.count(429),
                  "other": [c for c in codes if c not in (200, 429)], "seconds": round(time.time() - t0, 1)}))
