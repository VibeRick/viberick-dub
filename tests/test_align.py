from dub import align

WORDS = [{"w": "안녕하세요", "start": 0.0, "end": 1.0}, {"w": "바이브릭", "start": 1.2, "end": 2.0},
         {"w": "입니다", "start": 2.1, "end": 2.6}]


def test_norm_keeps_hangul_kana_cjk_latin():
    assert "".join(align.norm_chars("Hi, 안녕! カナ 漢字 SEO-2")) == "hi안녕カナ漢字seo2"


def test_retime_maps_corrected_lines_to_word_times():
    cues = align.retime(["안녕하세요.", "바이브릭입니다."], WORDS)
    assert [c["text"] for c in cues] == ["안녕하세요.", "바이브릭입니다."]
    assert cues[0]["start"] == 0.0 and abs(cues[1]["start"] - 1.2) < 0.01
    assert abs(cues[1]["end"] - 2.6) < 0.2


def test_retime_survives_a_corrected_word():
    # STT heard "바이블릭"; the proofread text says "바이브릭"
    words = [dict(WORDS[0]), {"w": "바이블릭", "start": 1.2, "end": 2.0}, dict(WORDS[2])]
    cues = align.retime(["안녕하세요", "바이브릭입니다"], words)
    assert abs(cues[1]["start"] - 1.2) < 0.01


def test_line_without_letters_merges_into_previous():
    cues = align.retime(["안녕하세요", "...", "바이브릭입니다"], WORDS)
    assert len(cues) == 2 and cues[0]["text"].endswith("...")


def test_devanagari_lines_get_their_own_timing():
    words = [{"w": "नमस्ते", "start": 0.0, "end": 0.5}, {"w": "दोस्तों।", "start": 0.5, "end": 1.0},
             {"w": "आज", "start": 3.0, "end": 3.3}, {"w": "बात", "start": 3.3, "end": 3.6}]
    cues = align.retime(["नमस्ते दोस्तों।", "आज बात"], words)
    assert len(cues) == 2 and cues[1]["start"] == 3.0
