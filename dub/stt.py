"""Chirp 3 (Speech-to-Text v2, location us) → word timings.

Batch with word timestamps is capped at 20 min, so longer audio is cut at silences into ≤18-min
chunks and the times are offset back. Sync recognize (<60 s) is used to cut paragraph TTS takes."""
import re
import logging
import subprocess
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech as cs

from . import config


def _creds():
    return config.gcp_credentials()


def _client() -> SpeechClient:
    # REST, not gRPC: gRPC channels hung when used from worker threads that also fork ffmpeg.
    return SpeechClient(credentials=_creds(), transport="rest", client_options=ClientOptions(
        api_endpoint=f"{config.STT_LOCATION}-speech.googleapis.com", quota_project_id=config.GCP_PROJECT))


def _cfg(lang: str, diarize: bool = False) -> cs.RecognitionConfig:
    feats = cs.RecognitionFeatures(enable_word_time_offsets=True, enable_automatic_punctuation=True)
    if diarize:
        feats.diarization_config = cs.SpeakerDiarizationConfig(min_speaker_count=1, max_speaker_count=6)
    return cs.RecognitionConfig(auto_decoding_config=cs.AutoDetectDecodingConfig(),
                                language_codes=[config.chirp_code(lang)], model="chirp_3", features=feats)


def chunk_bounds(duration: float, silences: list[tuple[float, float]],
                 max_len: float = 1080.0) -> list[tuple[float, float]]:
    bounds, start = [], 0.0
    while duration - start > max_len:
        cands = [(a + b) / 2 for a, b in silences if start + max_len * 0.5 < (a + b) / 2 <= start + max_len]
        cut = round(cands[-1], 3) if cands else start + max_len
        bounds.append((start, cut))
        start = cut
    bounds.append((start, duration))
    return bounds


def silences(audio: Path, noise_db: int = -35, min_sec: float = 0.6) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-i", str(audio), "-af", f"silencedetect=n={noise_db}dB:d={min_sec}",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def duration(audio: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(audio)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _words(results, offset: float, chunk: int | None = None) -> list[dict]:
    """chunk: speaker labels are only consistent within one recognition request, so they are scoped to it."""
    out = []
    for r in results:
        if r.alternatives:
            for w in r.alternatives[0].words:
                out.append({"w": w.word, "start": round(offset + w.start_offset.total_seconds(), 3),
                            "end": round(offset + w.end_offset.total_seconds(), 3),
                            **({"spk": w.speaker_label if chunk is None else f"{chunk}:{w.speaker_label}"}
                               if w.speaker_label else {})})
    return out


def chirp_words(audio: Path, lang: str, run_dir: Path) -> list[dict]:
    bucket = storage.Client(project=config.GCP_PROJECT, credentials=_creds()).bucket(config.BUCKET)
    words: list[dict] = []
    for i, (a, b) in enumerate(chunk_bounds(duration(audio), silences(audio))):
        part = run_dir / f"stt.part{i}.flac"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-to", str(b), "-i", str(audio),
                        "-c:a", "flac", str(part)], check=True)
        blob = bucket.blob(f"stt/{run_dir.name}/{part.name}")
        try:
            blob.upload_from_filename(part)
            uri = f"gs://{config.BUCKET}/{blob.name}"
            req = cs.BatchRecognizeRequest(
                recognizer=f"projects/{config.GCP_PROJECT}/locations/{config.STT_LOCATION}/recognizers/_",
                config=_cfg(lang, diarize=True), files=[cs.BatchRecognizeFileMetadata(uri=uri)],
                recognition_output_config=cs.RecognitionOutputConfig(inline_response_config=cs.InlineOutputConfig()))
            res = _client().batch_recognize(request=req).result(timeout=3600).results[uri]
            if res.error and res.error.code:
                raise RuntimeError(f"chirp_3 chunk {i}: {res.error.message}")
            words += _words(res.transcript.results, a, chunk=i)
        finally:
            # Cleanup failures must not hide recognition errors or discard a valid result.
            for cleanup in (blob.delete, lambda: part.unlink(missing_ok=True)):
                try:
                    cleanup()
                except Exception as error:
                    logging.getLogger(__name__).warning("STT chunk %s cleanup failed (%s)", i, type(error).__name__)

    return words


def spoken_language(audio: Path, total: float, seconds: float = 45.0) -> str | None:
    """The language actually spoken, heard by Chirp 3 on a clip near the start (not guessed from the title:
    an English title on a Hindi video sent a whole job down the English path). None when nothing is heard."""
    start = min(30.0, max(0.0, total * 0.2))
    clip = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(seconds), "-i", str(audio),
                           "-ac", "1", "-ar", "16000", "-c:a", "flac", "-f", "flac", "-"],
                          check=True, capture_output=True).stdout
    req = cs.RecognizeRequest(recognizer=f"projects/{config.GCP_PROJECT}/locations/{config.STT_LOCATION}/recognizers/_",
                              config=_cfg("auto"), content=clip)
    return heard_language(_client().recognize(request=req, timeout=120).results)


def heard_language(results) -> str | None:
    """The detected language that carries the most transcript text, in our codes."""
    weight: dict[str, int] = {}
    for r in results:
        code = config.source_code(r.language_code) if r.language_code else None
        text = r.alternatives[0].transcript if r.alternatives else ""
        if code and text.strip():
            weight[code] = weight.get(code, 0) + len(text)
    return max(weight, key=weight.get) if weight else None


def chirp_sync_words(wav_bytes: bytes, lang: str) -> list[dict]:
    req = cs.RecognizeRequest(
        recognizer=f"projects/{config.GCP_PROJECT}/locations/{config.STT_LOCATION}/recognizers/_",
        config=_cfg(lang), content=wav_bytes)
    return _words(_client().recognize(request=req, timeout=60).results, 0.0)
