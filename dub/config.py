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

GCP_PROJECT = "viberick"
GCP_ACCOUNT = "jaeho.shin@viberick.com"
BUCKET = os.environ.get("DUB_BUCKET", "viberick-dub-lab")
STT_LOCATION = "us"          # chirp_3 runs only in us / eu

LANGS = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh-Hans": "Chinese (Simplified)"}
CHIRP_CODES = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP", "zh-Hans": "cmn-Hans-CN"}


@cache
def gemini_key() -> str:
    if k := os.environ.get("GEMINI_API_KEY"):
        return k
    r = subprocess.run(["security", "find-generic-password", "-s", "gemini_api_key", "-w"],
                       capture_output=True, text=True)
    if not r.stdout.strip():
        raise RuntimeError("GEMINI_API_KEY not set and not in Keychain (gemini_api_key)")
    return r.stdout.strip()


@cache
def tts_key() -> str:
    """Gemini API key for TTS. The stored voice lives in this key's project (civil-oarlock, Tier 3:
    the viberick key is Tier 1 = 10 TTS requests/min)."""
    if k := os.environ.get("GEMINI_TTS_API_KEY"):
        return k
    r = subprocess.run(["security", "find-generic-password", "-s", "gemini_api_key_dub_tier3", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() or gemini_key()


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
