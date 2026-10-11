from tools.refine_underfill import better, select_rows


def test_selects_worst_underfill_skipping_short_filler_and_limits_each_language():
    units = [{"id": i, "start": 0, "end": (0.8 if i == 0 else 10)} for i in range(10)]
    rows = [{"id": i, "dur": i + 1, "slot": 10} for i in range(10)]
    assert [r["id"] for r in select_rows(rows, units)] == [1, 2, 3, 4, 5, 6]


def test_accepts_only_closer_clean_pass_without_slot_overflow():
    unit = {"start": 0, "end": 9, "slot": 10}
    original = {"dur": 6}
    good = {"dur": 8, "ok": True, "text": "Hello", "heard": "Hello"}
    assert better(good, original, unit, "en")[0]
    for changes in [{"dur": 5}, {"dur": 10.01}, {"ok": False}, {"text": "한국어"}, {"heard": "한국어"}]:
        assert not better({**good, **changes}, original, unit, "en")[0]


def test_duration_noise_is_not_counted_as_improvement():
    assert not better({"dur": 6.01, "ok": True, "text": "ok"}, {"dur": 6},
                      {"start": 0, "end": 9, "slot": 10}, "en")[0]
