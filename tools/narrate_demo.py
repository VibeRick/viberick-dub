"""Generate and check the consented creator's English demo narration under the shared approved ledger."""
import json
import os
from pathlib import Path

from dub import check, config, voice
from dub.budget import Budget
from tools.validate_voice import guarded_requests

SCRIPTS = {
    "opening": "I make videos in Korean. Reaching another audience should not mean losing my voice. Listen to the same sentence in four languages.",
    "studio": "VibeRick Dub gives creators a timeline they can inspect. Switch languages without losing your place. Compare each translation with the source, then preview an edit before accepting it.",
    "evidence": "In this earlier run, a Japanese line was flagged as Korean. The agent tried again, and the next listening check passed.",
    "closing": "Chirp supplies timestamps. Gemini translates, speaks, and checks the audio. Cloud Run runs the jobs. The creator reviews the result before publishing."
}


def main():
    if not all(os.environ.get(k) for k in ("GEMINI_API_KEY", "GEMINI_TTS_API_KEY")):
        raise ValueError("Explicit VibeRick environment keys are required; no keychain fallback")
    out = Path("demo/remotion/public/narration")
    if out.exists():
        raise ValueError("Narration directory already exists; preserve the previous takes")
    out.mkdir(parents=True)
    budget = Budget(100, {"tts": 500, "text": 500},
                    ledger_path=Path("runs/validation-budget-2026-10-10.json"), run_cap_usd=5)
    rows = {}
    try:
        with guarded_requests(budget, .20, .20):
            for name, text in SCRIPTS.items():
                path = out / f"{name}.wav"
                for attempt in range(2):
                    voice.synth(text, path, voice_id=config.VOICE_ID, lang="en")
                    verdict = check.check(path, text, "en", text, "en")
                    if all(verdict[k] is True for k in ("language_ok", "content_ok", "meaning_ok")):
                        break
                    path.rename(out / f"{name}.failed-{attempt}.wav")
                else:
                    raise RuntimeError(f"Narration check failed for {name}")
                rows[name] = {"text": text, "seconds": voice.duration(path), "verdict": verdict}
                (out / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
                print(name, round(rows[name]["seconds"], 2), "seconds; check passed", flush=True)
    finally:
        (out / "budget.json").write_text(json.dumps(budget.snapshot(), indent=2))


if __name__ == "__main__":
    main()
