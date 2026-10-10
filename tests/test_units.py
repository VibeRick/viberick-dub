from dub import units


def test_detect_language():
    assert units.detect_language("오늘은 SEO를 정리합니다") == "ko"
    assert units.detect_language("今日はSEOをまとめます") == "ja"
    assert units.detect_language("今天我们总结一下SEO") == "zh-Hans"
    assert units.detect_language("Today we cover SEO") == "en"


def test_targets_exclude_source():
    assert units.targets_for("ko") == ["en", "ja", "zh-Hans"]
    assert units.targets_for("en") == ["ko", "ja", "zh-Hans"]


def test_slots_extend_into_following_gap_but_not_forever():
    cues = [{"start": 0.0, "end": 2.0, "text": "a."}, {"start": 2.2, "end": 3.0, "text": "b."},
            {"start": 9.0, "end": 10.0, "text": "c."}]
    u = units.make_units(cues, duration=12.0)
    assert [x["id"] for x in u] == [0, 1, 2]
    assert u[0]["slot"] == 2.2          # up to the next start
    assert u[1]["slot"] == 1.6          # capped at end + 0.8
    assert u[2]["slot"] == 1.8          # last: end + 0.8, within duration


def test_flow_gaps_follow_source_continuity():
    us = [{"start": 0.0, "end": 1.0}, {"start": 1.2, "end": 2.0}, {"start": 3.0, "end": 4.0}]
    assert units.flow_gaps(us, [True, True, True], [False, False, False]) == [None, 0.0, None]
    assert units.flow_gaps(us, [False, False, False], [False, False, False]) == [None, units.FLOW_GAP, None]


def test_mid_sentence_breath_pause_flows_but_sentence_end_anchors():
    us = [{"start": 0.0, "end": 1.0}, {"start": 1.6, "end": 2.0}, {"start": 2.6, "end": 3.0}]
    texts = ["As businesses began to ponder", "these crucial questions.", "GEO emerged."]
    f = units.flow_gaps(us, [False] * 3, [False] * 3, texts)
    assert f == [None, units.FLOW_GAP, None]


def test_fragments_of_one_sentence_become_one_unit():
    cues = [{"start": 0.0, "end": 1.0, "text": "네, 오늘은"}, {"start": 1.2, "end": 2.9, "text": "SEO, AEO, GEO"},
            {"start": 3.2, "end": 5.6, "text": "이 세 가지 개념에 대해서 좀 확실히 알아보는"},
            {"start": 6.0, "end": 7.8, "text": "어, 그 시간을 가지려고 합니다."},
            {"start": 8.1, "end": 9.0, "text": "다음 문장."}]
    u = units.make_units(cues, duration=12.0)
    assert len(u) == 2
    assert u[0]["text"] == "네, 오늘은 SEO, AEO, GEO 이 세 가지 개념에 대해서 좀 확실히 알아보는 어, 그 시간을 가지려고 합니다."
    assert u[0]["start"] == 0.0 and u[0]["end"] == 7.8 and u[1]["id"] == 1


def test_sentence_merge_stops_at_long_pause_and_max_length():
    cues = [{"start": 0.0, "end": 1.0, "text": "그래서"}, {"start": 3.0, "end": 4.0, "text": "이건"}]
    assert len(units.make_units(cues, duration=5.0)) == 2          # 2 s pause: separate
    long = [{"start": i * 2.0, "end": i * 2.0 + 1.9, "text": f"조각{i}"} for i in range(12)]
    assert all(x["end"] - x["start"] <= units.MAX_UNIT_SEC for x in units.make_units(long, duration=30.0))
