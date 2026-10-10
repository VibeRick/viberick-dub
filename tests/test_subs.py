from dub import subs


def test_srt_splits_long_cjk_line_and_keeps_timing():
    out = subs.srt([{"start": 1.0, "end": 5.0}], ["这是一个非常非常长的中文字幕行，需要被拆分成两行来显示，才能让观众看清楚"], "zh-Hans")
    blocks = [b for b in out.strip().split("\n\n") if b]
    assert len(blocks) == 2
    assert blocks[0].splitlines()[1].startswith("00:00:01,000 --> ")
    assert blocks[-1].splitlines()[1].endswith("00:00:05,000")


def test_vtt_from_srt():
    v = subs.vtt("1\n00:00:01,000 --> 00:00:02,500\nhi\n")
    assert v.startswith("WEBVTT\n\n") and "00:00:01.000 --> 00:00:02.500" in v
