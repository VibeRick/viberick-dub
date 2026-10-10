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
    monkeypatch.setattr(voice, "_trim_fade", lambda raw, out: (out.write_bytes(raw), 0.6)[1])
    assert voice.synth("hello", tmp_path / "a.wav") == 0.6
    assert seq == []


def test_find_audio_nested_under_steps():
    blob = "A" * 2000
    assert voice._find_audio({"steps": [{"content": [{"type": "audio", "data": blob}]}]}) == blob


def test_dropped_connection_is_retried(monkeypatch):
    import http.client, io, json
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http.client.RemoteDisconnected("closed")
        return io.BytesIO(json.dumps({"steps": [{"data": "QUFB" * 400}]}).encode())
    monkeypatch.setattr(voice.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.setattr(voice.config, "tts_key", lambda: "k")
    assert len(voice._request("hi", "v")) > 0 and len(calls) == 2


def test_default_rate_is_the_measured_one():
    assert abs(voice.GATE.gap - 0.5) < 1e-9 or voice.os.environ.get("DUB_TTS_PER_MIN")
