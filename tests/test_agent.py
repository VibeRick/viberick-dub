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
