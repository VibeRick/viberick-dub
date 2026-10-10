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
    cues = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.2, "end": 3.0, "text": "b"},
            {"start": 9.0, "end": 10.0, "text": "c"}]
    u = units.make_units(cues, duration=12.0)
    assert [x["id"] for x in u] == [0, 1, 2]
    assert u[0]["slot"] == 2.2          # up to the next start
    assert u[1]["slot"] == 1.6          # capped at end + 0.8
    assert u[2]["slot"] == 1.8          # last: end + 0.8, within duration
