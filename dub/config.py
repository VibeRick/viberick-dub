"""Paths, model ids, languages, and credentials. Never prints secrets."""
import os
import subprocess
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("DUB_RUNS", ROOT / "runs"))

TEXT_MODEL = os.environ.get("DUB_TEXT_MODEL", "gemini-3.8-flash")
TTS_MODEL = os.environ.get("DUB_TTS_MODEL", "gemini-3.8-flash-tts")
VOICE_ID = os.environ.get("DUB_VOICE_ID", "voice_v6oqh4nu2jaw")   # Jaeho's replicated voice (Tier 3 project)
FALLBACK_VOICE = "Puck"
# Consent gate: the cloned voice is used only for channels whose owner recorded consent.
CONSENTED_CHANNELS = set(filter(None, os.environ.get("DUB_CONSENTED_CHANNELS", "UCtcp7RtJMf8hWCKScSctioA").split(",")))
ACTIVE = {"voice": VOICE_ID}   # one job per process; set by pipeline.main


def voice_for(info: dict) -> str:
    return VOICE_ID if info.get("channel_id") in CONSENTED_CHANNELS else FALLBACK_VOICE

GCP_PROJECT = os.environ.get("DUB_GCP_PROJECT", "viberick")
GCP_ACCOUNT = os.environ.get("DUB_GCP_ACCOUNT", "jaeho.shin@viberick.com")
BUCKET = os.environ.get("DUB_BUCKET", "viberick-dub-lab")
STT_LOCATION = "us"          # chirp_3 runs only in us / eu

LANGS = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh-Hans": "Chinese (Simplified)"}
CHIRP_CODES = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP", "zh-Hans": "cmn-Hans-CN"}


@cache
def gemini_key() -> str:
    """Use only an explicitly supplied key; never search other projects or Keychain."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY explicitly from this project's approved secret source")
    return key


@cache
def tts_key() -> str:
    """TTS and stored voices must belong to the explicitly configured TTS project."""
    key = os.environ.get("GEMINI_TTS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Set GEMINI_TTS_API_KEY explicitly from the approved project that owns the voice")
    return key


def gcp_token() -> str:
    """Access token for the viberick account. Not cached: tokens expire after ~1 h."""
    if t := os.environ.get("GCP_TOKEN"):
        return t
    r = subprocess.run(["gcloud", "auth", "print-access-token", "--account", GCP_ACCOUNT],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def gcp_credentials():
    """Locally: the viberick gcloud account's token (never the Mac's ADC, which is another venture).
    On Cloud Run (K_SERVICE / CLOUD_RUN_JOB set): the attached service account."""
    if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"):
        import google.auth
        return google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0]
    from google.oauth2.credentials import Credentials
    return Credentials(gcp_token())
