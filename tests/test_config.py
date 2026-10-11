"""Credential lookup must never silently cross account or project boundaries."""
import pytest
from dub import config


@pytest.fixture(autouse=True)
def clear_key_caches():
    config.gemini_key.cache_clear()
    config.tts_key.cache_clear()
    yield
    config.gemini_key.cache_clear()
    config.tts_key.cache_clear()


def test_missing_keys_do_not_search_keychain_or_fall_back(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_TTS_API_KEY", raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("Credential lookup must not launch a subprocess")
    monkeypatch.setattr(config.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        config.gemini_key()
    # A text key does not authorize billing the same project for voice synthesis.
    monkeypatch.setenv("GEMINI_API_KEY", "test-text-placeholder")
    with pytest.raises(RuntimeError, match="GEMINI_TTS_API_KEY"):
        config.tts_key()


def test_explicit_keys_are_independent_and_nonempty(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", " test-text-placeholder ")
    monkeypatch.setenv("GEMINI_TTS_API_KEY", " test-tts-placeholder ")
    assert config.gemini_key() == "test-text-placeholder"
    assert config.tts_key() == "test-tts-placeholder"
    config.tts_key.cache_clear()
    monkeypatch.setenv("GEMINI_TTS_API_KEY", "  ")
    with pytest.raises(RuntimeError):
        config.tts_key()
