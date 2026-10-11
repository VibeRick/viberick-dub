import json
from tools import build_studio_review


def test_fixture_uses_source_title_and_preserves_speaker_metadata(tmp_path, monkeypatch):
    run = tmp_path / "conversation"
    out = run / "out"
    out.mkdir(parents=True)
    speakers = {"a": {"name": "Test speaker", "voice_type": "preset"}}
    (run / "info.json").write_text(json.dumps({"title": "Conversation test", "speakers": speakers, "source_captioned": False, "source_url": "https://youtu.be/test?t=30", "source_interval": {"start": 30, "end": 70}, "voice_disclosure": "Preset voices only"}))
    (out / "report.json").write_text(json.dumps({"src": "en", "video": "test", "langs": [{"lang": "ko"}]}))
    (run / "events.jsonl").write_text("")
    (run / "source-alignment.json").write_text(json.dumps({"method": "Audio-estimated prepared turns"}))
    for lang in ("orig", "ko"):
        (out / f"video.{lang}.mp4").write_bytes(b"fixture")
    monkeypatch.setattr(build_studio_review, "result_document", lambda *_: {"rows": [{"id": 0, "spk": "a"}]})
    manifest = json.loads(build_studio_review.build(run, tmp_path / "review").read_text())
    assert manifest["job"]["title"] == "Conversation test"
    assert manifest["job"]["url"] == "https://youtu.be/test?t=30"
    assert manifest["job"]["source_interval"] == {"start": 30, "end": 70}
    assert manifest["job"]["validation_scope"] == "prepared_source_turns"
    assert manifest["job"]["voice_disclosure"] == "Preset voices only"
    assert manifest["job"]["source_captioned"] is False
    assert manifest["job"]["report"]["speakers"] == speakers
    assert manifest["lines"]["ko"]["rows"][0]["spk"] == "a"
    # An uninspected source must not be claimed to have (or lack) burned captions.
    (run / "info.json").write_text(json.dumps({"title": "Uninspected source"}))
    manifest = json.loads(build_studio_review.build(run, tmp_path / "review2").read_text())
    assert manifest["job"]["source_captioned"] is None
