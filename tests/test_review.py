from dub import review


def test_review_is_skipped_when_web_assets_are_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(review, "WEB", tmp_path / "nowhere")
    assert review.write(tmp_path, tmp_path / "source.wav", [], []) is None
