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


def test_paragraph_lines_are_never_slowed():
    assert fit.decide_tempo(1.0, 2.0, allow_slow=False) == 1.0
    assert abs(fit.decide_tempo(2.2, 2.0, allow_slow=False) - 1.1) < 1e-6


def test_stretch_fades_clip_edges(tmp_path):
    import struct, wave
    from dub import voice
    src = tmp_path / "loud.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(voice.RATE)
        w.writeframes(struct.pack("<h", 20000) * voice.RATE)
    fit.stretch(src, tmp_path / "out.wav", 1.0)
    pcm = voice.pcm(tmp_path / "out.wav")
    first, last = struct.unpack("<h", pcm[:2])[0], struct.unpack("<h", pcm[-2:])[0]
    assert abs(first) < 2000 and abs(last) < 2000
