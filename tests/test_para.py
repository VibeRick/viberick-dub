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
