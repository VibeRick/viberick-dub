from dub import agent


def test_agent_shortens_then_retries_then_accepts(monkeypatch, tmp_path):
    durs = iter([3.0, 2.2, 2.2])                 # too long → shorter → resynth after failed check
    monkeypatch.setattr(agent.voice, "synth", lambda text, out, **k: (out.write_bytes(b"x"), next(durs))[1])
    monkeypatch.setattr(agent.translate, "shorten", lambda *a: "short line")
    monkeypatch.setattr(agent.fit, "stretch", lambda s, d, t: d.write_bytes(b"x") or 2.0)
    verdicts = iter([{"heard": "", "language_ok": True, "content_ok": False, "issue": "garbled"},
                     {"heard": "short line", "language_ok": True, "content_ok": True, "issue": ""}])
    monkeypatch.setattr(agent.check, "check", lambda *a: next(verdicts))
    monkeypatch.setattr(agent.check, "audible", lambda p: True)
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    u = {"id": 0, "text": "원문", "slot": 2.0}
    row = agent.repair_line(u, "a long long line", "ko", "en", {}, tmp_path, tmp_path, pre=False)
    assert row["ok"] and row["text"] == "short line"
    assert [a["do"] for a in row["actions"]] == ["synth", "shorten", "synth", "check", "resynth", "check"]


def test_silent_clip_fails_without_asking_gemini(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.voice, "synth", lambda text, out, **k: (out.write_bytes(b"x"), 1.8)[1])
    monkeypatch.setattr(agent.fit, "stretch", lambda s, d, t: (d.write_bytes(b"x"), 1.8)[1])
    audible = iter([False, True])
    monkeypatch.setattr(agent.check, "audible", lambda p: next(audible))
    asked = []
    monkeypatch.setattr(agent.check, "check", lambda *a: asked.append(1) or {"heard": "x", "language_ok": True,
                                                                              "content_ok": True, "issue": ""})
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 0, "text": "원문", "slot": 2.0}, "line", "ko", "en", {}, tmp_path, tmp_path, pre=False)
    assert row["ok"] and len(asked) == 1
    assert [a["do"] for a in row["actions"]] == ["synth", "check", "resynth", "check"]


def test_short_yes_is_audible(tmp_path):
    import struct, wave
    p = tmp_path / "yes.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(struct.pack("<h", 4000) * int(24000 * 0.2) + struct.pack("<h", 0) * 2400)
    assert agent.check.audible(p)


def test_shorten_that_guts_the_line_is_rejected(monkeypatch, tmp_path):
    durs = iter([2.0])
    monkeypatch.setattr(agent.voice, "synth", lambda text, out, **k: (out.write_bytes(b"x"), next(durs))[1])
    monkeypatch.setattr(agent.translate, "shorten", lambda *a: "あ")
    monkeypatch.setattr(agent.fit, "stretch", lambda s, d, t: (d.write_bytes(b"x"), 0.7)[1])
    monkeypatch.setattr(agent.check, "audible", lambda p: True)
    monkeypatch.setattr(agent.check, "check", lambda *a: {"heard": "x", "language_ok": True, "content_ok": True, "issue": ""})
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 0, "text": "원문", "slot": 0.6}, "そうですね", "ko", "ja", {}, tmp_path, tmp_path, pre=False)
    assert row["text"] == "そうですね"
    assert [a["do"] for a in row["actions"]] == ["synth", "check"]
