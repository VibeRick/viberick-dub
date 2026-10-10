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
