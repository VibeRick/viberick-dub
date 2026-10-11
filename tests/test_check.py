import pytest

from dub import check


@pytest.mark.parametrize("value", [
    {"heard": "hello", "language_ok": True, "content_ok": True, "issue": ""},
    {"heard": "hello", "language_ok": True, "content_ok": True, "meaning_ok": "false", "issue": ""},
    {"heard": "hello", "language_ok": 1, "content_ok": True, "meaning_ok": True, "issue": ""},
    None,
])
def test_incomplete_or_nonboolean_verdict_never_passes(value):
    verdict = check.normalize_verdict(value)
    assert not verdict["meaning_ok"] and not verdict["content_ok"]


def test_bad_verdict_retries_listening_without_resynthesis(monkeypatch, tmp_path):
    clip = tmp_path / "line.wav"
    clip.write_bytes(b"mock audio")
    valid = {"heard": "hello", "language_ok": True, "content_ok": True, "meaning_ok": True, "issue": ""}
    responses = iter([{"heard": "hello"}, valid])
    monkeypatch.setattr(check.gem, "json_call", lambda *a, **k: next(responses))
    assert check.check(clip, "hello", "en", "안녕", "ko") == valid
