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


def test_synth_group_rejects_cut_past_take_end(monkeypatch, tmp_path):
    from dub import voice
    monkeypatch.setattr(para.voice, "synth", lambda text, out: (out.write_bytes(voice._silence_wav(1.0)), 1.0)[1])
    words = [{"w": "Hello", "start": 0.1, "end": 0.5}, {"w": "there.", "start": 2.0, "end": 2.4}]
    monkeypatch.setattr(para.stt, "chirp_sync_words", lambda b, lang: words)
    assert para.synth_group(["Hello", "there."], "en", tmp_path, [0, 1]) is False


def test_quiet_point_snaps_to_lowest_energy():
    import struct
    rate = 1000
    loud, quiet = struct.pack("<h", 15000), struct.pack("<h", 10)
    pcm = loud * 500 + quiet * 40 + loud * 460          # quiet 0.50–0.54 s
    t = para.quiet_point(pcm, 0.6, rate, search=0.15)
    assert 0.5 <= t <= 0.54
