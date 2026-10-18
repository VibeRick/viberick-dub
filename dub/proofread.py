"""Gemini listens to the audio and corrects Chirp's transcript; line breaks at natural pauses.
Timing is NOT taken from Gemini: the corrected lines are re-timed onto Chirp's words (align.retime).
Measured on Fty2sz3dBwU: CER 7.6–7.9 % vs 8.6 % Chirp alone, timing p50 0.22 s, no drift."""
import subprocess
from pathlib import Path

from google.genai import types

from . import align, config, gem


def _opus(audio: Path) -> bytes:
    """16 kHz mono Opus at 24 kbps: ~11 MB/hour, well under the inline request limit."""
    out = audio.with_suffix(".proof.ogg")
    if not out.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-ac", "1", "-ar", "16000",
                        "-c:a", "libopus", "-b:a", "24k", str(out)], check=True)
    return out.read_bytes()


def proofread(audio: Path, words: list[dict], info: dict, lang: str) -> list[dict]:
    draft = " ".join(w["w"] for w in words)
    prompt = (
        f"Below is a machine transcript of this {config.LANGS[lang]} YouTube video "
        f"(channel {info.get('channel')!r}; title {info.get('title')!r}; tags {info.get('tags') or []}).\n"
        "Listen to the audio and return the corrected transcript: fix misheard words, brand and tech terms "
        "(use the channel name, title and tags as ground truth for names), and spacing. Keep the speaker's "
        "actual words in order; do not paraphrase, summarize or drop anything. Put a line break at every "
        "natural pause: one subtitle-length phrase per line. Output only the transcript.\n\n" + draft)
    # The whole transcript comes back in one answer, so a normal call is longer: hedge later.
    text = gem.text_call(prompt, parts=[types.Part.from_bytes(data=_opus(audio), mime_type="audio/ogg")],
                         hedge_after=(45.0, 90.0))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cues = align.retime(lines, words)
    return cues or align.retime([draft], words)
