from dub import agent


def test_agent_shortens_then_retries_then_accepts(monkeypatch, tmp_path):
    durs = iter([3.0, 2.2, 2.2])                 # too long → shorter → resynth after failed check
    monkeypatch.setattr(agent.voice, "synth", lambda text, out, **k: (out.write_bytes(b"x"), next(durs))[1])
    monkeypatch.setattr(agent.translate, "shorten", lambda *a: "short line")
    monkeypatch.setattr(agent.fit, "stretch", lambda s, d, t: d.write_bytes(b"x") or 2.0)
    verdicts = iter([{"heard": "", "language_ok": True, "content_ok": False, "meaning_ok": True, "issue": "garbled"},
                     {"heard": "short line", "language_ok": True, "content_ok": True, "meaning_ok": True, "issue": ""}])
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
                                                                              "content_ok": True, "meaning_ok": True, "issue": ""})
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
    monkeypatch.setattr(agent.check, "check", lambda *a: {"heard": "x", "language_ok": True, "content_ok": True, "meaning_ok": True, "issue": ""})
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 0, "text": "원문", "slot": 0.6}, "そうですね", "ko", "ja", {}, tmp_path, tmp_path, pre=False)
    assert row["text"] == "そうですね"
    assert [a["do"] for a in row["actions"]] == ["synth", "check"]


def test_empty_translation_becomes_a_silent_skip(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.voice, "synth", lambda *a, **k: (_ for _ in ()).throw(AssertionError("synth on empty")))
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 3, "text": "음…", "slot": 1.0}, "", "ko", "en", {}, tmp_path, tmp_path, pre=False)
    assert row["ok"] and [a["do"] for a in row["actions"]] == ["skip"]
    assert abs(agent.voice.duration(tmp_path / "0003.wav") - 0.3) < 0.01


def test_empty_meaningful_translation_is_flagged_without_synthesis(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.voice, "synth", lambda *a, **k: (_ for _ in ()).throw(AssertionError("paid call")))
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 1, "text": "가격은 만 원입니다", "slot": 2}, "", "ko", "en", {},
                            tmp_path, tmp_path, False)
    assert not row["ok"] and "meaningful" in row["issue"]


def test_script_leak_is_repaired_before_speech_and_invalidates_precomputed_take(monkeypatch, tmp_path):
    spoken = []
    monkeypatch.setattr(agent.translate, "_batch", lambda *a: ["Search Google"])
    monkeypatch.setattr(agent.voice, "synth", lambda t, p, **kw: (spoken.append((t, kw)), p.write_bytes(b"audio"), 1.8)[-1])
    monkeypatch.setattr(agent.fit, "stretch", lambda s, p, t: (p.write_bytes(b"audio"), 1.8)[-1])
    monkeypatch.setattr(agent.check, "audible", lambda p: True)
    monkeypatch.setattr(agent.check, "check", lambda *a: {"heard":"Search Google", "language_ok":True,
                                                         "content_ok":True, "meaning_ok":True, "issue":""})
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 0, "text":"구글링", "slot":2}, "Try 구글링", "ko", "en", {},
                            tmp_path, tmp_path, True)
    assert row["ok"] and spoken[0][0] == "Search Google" and spoken[0][1]["lang"] == "en"


def test_meaning_failure_is_not_a_pass_and_failed_audio_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.translate, "_batch", lambda *a: ["It does not work"])
    monkeypatch.setattr(agent.voice, "synth", lambda t, p, **kw: (p.write_bytes(b"audio"), 1.8)[-1])
    monkeypatch.setattr(agent.fit, "stretch", lambda s, p, t: (p.write_bytes(b"final"), 1.8)[-1])
    monkeypatch.setattr(agent.check, "audible", lambda p: True)
    verdicts = iter([False, True])
    def listen(*args):
        assert args[3:] == ("안 됩니다", "ko")
        ok = next(verdicts)
        return {"heard":"It works", "language_ok":True, "content_ok":True, "meaning_ok":ok,
                "issue":"" if ok else "Negation lost"}
    monkeypatch.setattr(agent.check, "check", listen)
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row = agent.repair_line({"id": 0, "text":"안 됩니다", "slot":2}, "It works", "ko", "en", {},
                            tmp_path, tmp_path, False)
    failed = next(a for a in row["actions"] if a["do"] == "check" and not a["ok"])
    assert row["ok"] and row["text"] == "It does not work"
    assert (tmp_path / failed["audio_file"]).read_bytes() == b"final"


def test_underfill_uses_measured_duration_and_keeps_better_fit(monkeypatch, tmp_path):
    durations = iter([1.0, 2.7])
    monkeypatch.setattr(agent.voice, "synth", lambda t, p, **kw: (p.write_bytes(b"audio"), next(durations))[-1])
    measured = []
    monkeypatch.setattr(agent.translate, "fuller", lambda u,t,l,d,b: measured.append(d) or "This is a full translation")
    monkeypatch.setattr(agent.fit, "stretch", lambda s,p,t: (p.write_bytes(b"audio"), 2.7)[-1])
    monkeypatch.setattr(agent.check, "audible", lambda p: True)
    monkeypatch.setattr(agent.check, "check", lambda *a: {"heard":"", "language_ok":True,"content_ok":True,
                                                         "meaning_ok":True,"issue":""})
    monkeypatch.setattr(agent.events, "log", lambda *a, **k: None)
    row=agent.repair_line({"id":0,"text":"모든 의미를 보존합니다","slot":3},"Short line","ko","en",{},tmp_path,tmp_path,False)
    assert measured == [1.0] and row["text"] == "This is a full translation"
    assert any(a["do"] == "lengthen" for a in row["actions"])


def test_manual_underfilled_text_is_not_rewritten_on_meaning_failure(monkeypatch, tmp_path):
    spoken=[]
    def forbidden(*a,**kw): raise AssertionError('manual text rewrite attempted')
    for name in ('fuller','shorten','_batch'):
        monkeypatch.setattr(agent.translate,name,forbidden)
    monkeypatch.setattr(agent.voice,'synth',lambda text,p,**kw: (spoken.append(text),p.write_bytes(agent.voice._silence_wav(.3)),.3)[-1])
    monkeypatch.setattr(agent.fit,'stretch',lambda src,p,tempo: (p.write_bytes(agent.voice._silence_wav(.3)),.3)[-1])
    monkeypatch.setattr(agent.check,'audible',lambda p:True)
    monkeypatch.setattr(agent.check,'check',lambda *a:{'heard':'Brief edit','language_ok':True,'content_ok':True,
                                                      'meaning_ok':False,'issue':'Manual edit differs from source meaning'})
    monkeypatch.setattr(agent.events,'log',lambda *a,**kw:None)
    row=agent.repair_line({'id':0,'text':'Long original meaning','slot':3},'Brief edit','en','en',{},tmp_path,tmp_path,False,
                          preserve_user_text=True)
    assert spoken == ['Brief edit']*3
    assert row['text']=='Brief edit' and not row['ok'] and 'source meaning' in row['issue']
    assert not any(a['do'] in {'lengthen','shorten','retranslate'} for a in row['actions'])


def test_manual_long_text_flags_timing_without_shortening(monkeypatch,tmp_path):
    def forbidden(*a,**kw): raise AssertionError('manual text rewrite attempted')
    for name in ('fuller','shorten','_batch'): monkeypatch.setattr(agent.translate,name,forbidden)
    monkeypatch.setattr(agent.voice,'synth',lambda text,p,**kw:(p.write_bytes(agent.voice._silence_wav(3)),3)[-1])
    monkeypatch.setattr(agent.fit,'stretch',lambda src,p,tempo:(p.write_bytes(agent.voice._silence_wav(2.2)),2.2)[-1])
    monkeypatch.setattr(agent.check,'audible',lambda p:True)
    monkeypatch.setattr(agent.check,'check',lambda *a:{'heard':'Manual text','language_ok':True,'content_ok':True,'meaning_ok':True,'issue':''})
    monkeypatch.setattr(agent.events,'log',lambda *a,**kw:None)
    row=agent.repair_line({'id':0,'text':'source','slot':1},'Manual text','en','en',{},tmp_path,tmp_path,False,preserve_user_text=True)
    assert row['text']=='Manual text' and not row['ok'] and 'exceeds' in row['issue']
