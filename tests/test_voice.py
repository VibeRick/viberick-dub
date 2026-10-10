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


def test_find_audio_nested_under_steps():
    blob = "A" * 2000
    assert voice._find_audio({"steps": [{"content": [{"type": "audio", "data": blob}]}]}) == blob
