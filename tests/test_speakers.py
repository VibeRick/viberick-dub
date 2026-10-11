from dub import speakers, units


WORDS = [{"w": "a", "start": 0.0, "end": 0.5, "spk": "1"}, {"w": "b", "start": 0.6, "end": 1.0, "spk": "1"},
         {"w": "c", "start": 1.2, "end": 1.8, "spk": "2"}, {"w": "d", "start": 1.9, "end": 2.5, "spk": "2"}]


def test_cue_speaker_is_majority_of_its_words():
    cues = [{"start": 0.0, "end": 1.0, "text": "a b"}, {"start": 1.2, "end": 2.5, "text": "c d"}]
    assert [c["spk"] for c in speakers.label_cues(cues, WORDS)] == ["1", "2"]


def test_sentences_never_merge_across_speakers():
    cues = [{"start": 0.0, "end": 1.0, "text": "so", "spk": "1"}, {"start": 1.1, "end": 2.0, "text": "right", "spk": "2"}]
    assert len(units.sentences(cues)) == 2


def test_unchecked_speakers_never_get_clone():
    us = [{"spk": "1", "start": 0, "end": 10}, {"spk": "2", "start": 10, "end": 12}, {"spk": "3", "start": 12, "end": 13}]
    cast = speakers.default_cast(us, clone="voice_me", consent=True)
    assert "voice_me" not in cast.values() and len(set(cast.values())) == 3


def test_no_consent_means_no_clone_for_anyone():
    us = [{"spk": "1", "start": 0, "end": 10}]
    assert speakers.default_cast(us, clone="voice_me", consent=False)["1"] != "voice_me"


def test_clone_goes_to_verified_speaker_not_the_loudest():
    us = [{"spk": "1", "start": 0, "end": 10}, {"spk": "2", "start": 10, "end": 12}]
    cast = speakers.default_cast(us, clone="voice_me", consent=True, verified={"2"})
    assert cast["2"] == "voice_me" and cast["1"] != "voice_me"


def test_no_verified_speaker_means_no_clone():
    us = [{"spk": "1", "start": 0, "end": 10}]
    assert speakers.default_cast(us, clone="voice_me", consent=True, verified=set())["1"] != "voice_me"


def test_clone_uses_best_match_not_longest_speaker():
    us = [{"spk": "1", "start": 0, "end": 100}, {"spk": "2", "start": 100, "end": 110}]
    cast = speakers.default_cast(us, "clone", True, scores={"1": 0.60, "2": 0.85})
    assert cast["2"] == "clone" and cast["1"] != "clone"


def test_ambiguous_identity_falls_back_to_presets():
    us = [{"spk": "1", "start": 0, "end": 10}, {"spk": "2", "start": 10, "end": 12}]
    assert "clone" not in speakers.default_cast(us, "clone", True, scores={"1": 0.80, "2": 0.78}).values()
    assert "clone" not in speakers.default_cast(us, "clone", True, verified={"1", "2"}).values()


def test_verified_owner_can_recur_with_different_chunk_labels():
    us = [{"spk": s, "start": i, "end": i + 1} for i, s in enumerate(["0:1", "0:2", "1:1", "1:2"])]
    cast = speakers.default_cast(us, "clone", True, scores={"0:1": 0.8, "0:2": 0.2, "1:1": 0.1, "1:2": 0.9})
    assert {s for s, v in cast.items() if v == "clone"} == {"0:1", "1:2"}


def test_nonfinite_scores_cannot_verify_identity():
    us = [{"spk": "1", "start": 0, "end": 10}]
    for score in (float("nan"), float("inf"), 0.1):
        assert "clone" not in speakers.default_cast(us, "clone", True, scores={"1": score}).values()


def test_many_chunk_speakers_do_not_exhaust_preset_rotation():
    us = [{"spk": str(i), "start": i, "end": i + 1} for i in range(100)]
    assert len(speakers.default_cast(us, "clone", False)) == 100


def test_cast_uses_scores_and_reports_the_matched_owner(tmp_path, monkeypatch):
    us = [{"spk": "1", "start": 0, "end": 100}, {"spk": "2", "start": 100, "end": 110}]
    monkeypatch.setattr(speakers, "verify_speakers", lambda *args: {"1": 0.55, "2": 0.85})
    cast = speakers.cast(us, None, "clone", True, tmp_path)
    assert cast["2"]["voice"] == "clone" and cast["1"]["voice"] != "clone"
    assert cast["2"]["match"] == 0.85


def test_cast_without_verification_never_clones(tmp_path, monkeypatch):
    monkeypatch.setattr(speakers, "verify_speakers", lambda *args: None)
    cast = speakers.cast([{"spk": "1", "start": 0, "end": 10}], None, "clone", True, tmp_path)
    assert cast["1"]["voice"] != "clone"
