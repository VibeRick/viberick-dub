from dub import fit


def test_needs_shorter_only_past_max_overrun():
    assert not fit.needs_shorter(2.4, 2.0) and fit.needs_shorter(2.6, 2.0)


def test_finish_keeps_speed_and_fades_clip_edges(tmp_path):
    import struct, wave
    from dub import voice
    src = tmp_path / "loud.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(voice.RATE)
        w.writeframes(struct.pack("<h", 20000) * voice.RATE)
    assert abs(fit.finish(src, tmp_path / "out.wav") - 1.0) < 0.005   # never sped up or slowed
    pcm = voice.pcm(tmp_path / "out.wav")
    first, last = struct.unpack("<h", pcm[:2])[0], struct.unpack("<h", pcm[-2:])[0]
    assert abs(first) < 2000 and abs(last) < 2000
