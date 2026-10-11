from dub import stt


def test_short_audio_is_one_chunk():
    assert stt.chunk_bounds(900.0, []) == [(0.0, 900.0)]


def test_long_audio_cuts_at_silence_before_limit():
    sil = [(500.0, 501.0), (1000.0, 1001.2), (1500.0, 1500.8)]
    b = stt.chunk_bounds(2000.0, sil, max_len=1080.0)
    assert b[0] == (0.0, 1000.6) and b[-1][1] == 2000.0
    assert all(e - s <= 1080.0 for s, e in b)


def test_long_audio_without_silence_hard_cuts():
    b = stt.chunk_bounds(2500.0, [], max_len=1080.0)
    assert b == [(0.0, 1080.0), (1080.0, 2160.0), (2160.0, 2500.0)]


class _W:
    def __init__(self, word, a, b, spk):
        import datetime
        self.word, self.speaker_label = word, spk
        self.start_offset, self.end_offset = datetime.timedelta(seconds=a), datetime.timedelta(seconds=b)


class _Alt:
    def __init__(self, words): self.words = words


class _Res:
    def __init__(self, words): self.alternatives = [_Alt(words)]


def test_speaker_labels_are_scoped_to_their_chunk():
    w = stt._words([_Res([_W("hi", 0.0, 0.5, "1")])], offset=1000.0, chunk=1)
    assert w[0]["spk"] == "1:1" and w[0]["start"] == 1000.0


from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock
import pytest


@pytest.mark.parametrize("recognition_fails,cleanup_fails", [(False, False), (True, False), (True, True), (False, True)])
def test_uploaded_chunk_is_cleaned_up_even_when_recognition_fails(tmp_path, monkeypatch, recognition_fails, cleanup_fails):
    blob = Mock(name="blob")
    blob.name = "stt/test/part.flac"
    if cleanup_fails:
        blob.delete.side_effect = RuntimeError("private cleanup details")
    bucket = Mock()
    bucket.blob.return_value = blob
    monkeypatch.setattr(stt.storage, "Client", lambda **kw: SimpleNamespace(bucket=lambda _: bucket))
    monkeypatch.setattr(stt, "_creds", lambda: None)
    monkeypatch.setattr(stt, "duration", lambda _: 1)
    monkeypatch.setattr(stt, "silences", lambda _: [])
    monkeypatch.setattr(stt.subprocess, "run", lambda args, **kw: Path(args[-1]).touch())
    result = SimpleNamespace(error=None, transcript=SimpleNamespace(results=[]))
    operation = Mock()
    if recognition_fails:
        operation.result.side_effect = RuntimeError("recognition failed")
    else:
        operation.result.return_value = SimpleNamespace(results={f"gs://{stt.config.BUCKET}/{blob.name}": result})
    monkeypatch.setattr(stt, "_client", lambda: SimpleNamespace(batch_recognize=lambda **kw: operation))
    if recognition_fails:
        with pytest.raises(RuntimeError, match="recognition failed"):
            stt.chirp_words(tmp_path / "input.wav", "en", tmp_path)
    else:
        assert stt.chirp_words(tmp_path / "input.wav", "en", tmp_path) == []
    blob.delete.assert_called_once()
    assert not (tmp_path / "stt.part0.flac").exists()
