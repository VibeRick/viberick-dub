from dub import speakers, units


WORDS = [{"w": "a", "start": 0.0, "end": 0.5, "spk": "1"}, {"w": "b", "start": 0.6, "end": 1.0, "spk": "1"},
         {"w": "c", "start": 1.2, "end": 1.8, "spk": "2"}, {"w": "d", "start": 1.9, "end": 2.5, "spk": "2"}]


def test_cue_speaker_is_majority_of_its_words():
    cues = [{"start": 0.0, "end": 1.0, "text": "a b"}, {"start": 1.2, "end": 2.5, "text": "c d"}]
    assert [c["spk"] for c in speakers.label_cues(cues, WORDS)] == ["1", "2"]


def test_sentences_never_merge_across_speakers():
    cues = [{"start": 0.0, "end": 1.0, "text": "so", "spk": "1"}, {"start": 1.1, "end": 2.0, "text": "right", "spk": "2"}]
    assert len(units.sentences(cues)) == 2


def test_main_speaker_gets_clone_others_get_presets():
    us = [{"spk": "1", "start": 0, "end": 10}, {"spk": "2", "start": 10, "end": 12}, {"spk": "3", "start": 12, "end": 13}]
    cast = speakers.default_cast(us, clone="voice_me", consent=True)
    assert cast["1"] == "voice_me" and cast["2"] != cast["3"] and "voice_me" not in (cast["2"], cast["3"])


def test_no_consent_means_no_clone_for_anyone():
    us = [{"spk": "1", "start": 0, "end": 10}]
    assert speakers.default_cast(us, clone="voice_me", consent=False)["1"] != "voice_me"
