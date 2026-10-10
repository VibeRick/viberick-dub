from dub import stt


def test_short_audio_is_one_chunk():
    assert stt.chunk_bounds(900.0, []) == [(0.0, 900.0)]


def test_long_audio_cuts_at_silence_before_limit():
    sil = [(500.0, 501.0), (1000.0, 1001.2), (1500.0, 1500.8)]
    b = stt.chunk_bounds(2000.0, sil, max_len=1080.0)
    assert b[0] == (0.0, 1000.6) and b[-1][1] == 2000.0
    assert all(e - s <= 1080.0 for s, e in b)


def test_long_audio_without_silence_hard_cuts():
    b = stt.chunk_bounds(2500.0, [], max_len=1080.0)
    assert b == [(0.0, 1080.0), (1080.0, 2160.0), (2160.0, 2500.0)]
