# VibeRick Dub

**Paste a YouTube link. Get it back in up to 125 languages, in your own voice.**

VibeRick Dub is an AI dubbing agent on Google Cloud. It transcribes a video, translates each sentence to fit the
seconds it was spoken in, speaks it in the creator's own voice (with consent) or a matched voice for every other
speaker, then listens to every line it made and fixes what is wrong before a person sees it.

- Live app: https://viberick-dub.web.app
- Team VibeRick · Google Cloud AI Builder Cup 2026 · Media, Content & Digital Experiences

## What it does

```
YouTube link + up to 4 target languages
  → download (Cloud Run Job) → demucs separates speech from music
  → Chirp 3: every word with a timestamp, plus speaker labels
  → Gemini 3.8 Flash listens to the audio, corrects the transcript, writes a dubbing brief (tone, terms)
  → voice casting: the creator's cloned voice only behind two consent locks; Gemini picks a matching preset for everyone else
  → Gemini translates each sentence to a character budget from its time slot and the voice's measured speed
  → Gemini TTS speaks each line
  → per-line agent loop: measure → shorten → time-fit → Gemini listens (language, words, meaning, length)
       → re-speak → re-translate → after 4 tries, flag for a human
  → mixed on the original timeline over the music bed (−14 LUFS) → MP4 + M4A per language, SRT/VTT
```

Every agent decision is written to Firestore, so the studio shows the agent working live. A creator can edit any
line, hear a preview in the same voice, and accept it; only that line is regenerated.

## Google Cloud

| Service | Role |
|---|---|
| Gemini 3.8 Flash (Vertex AI) | Listens to the audio to fix the transcript; dubbing brief; time-budgeted translation; listens to every dubbed line; casts voices |
| Gemini TTS voice replication | The creator's own voice in other languages; presets for other speakers (SynthID watermarked) |
| Chirp 3 (Speech-to-Text v2) | Word timestamps and speaker diarization: the timing backbone |
| Cloud Run service + Cloud Run Jobs | FastAPI API; one worker execution per dub (4 vCPU) |
| Firestore | Jobs, the live agent event stream, per-line results, edits |
| Firebase Hosting | The studio; `/api/**` is rewritten to Cloud Run |
| Cloud Storage | Published MP4/M4A/SRT/VTT; public job outputs expire after 7 days |
| Secret Manager · Artifact Registry · Cloud Build | Keys, container image, builds |

## Results (real cloud jobs)

| Run | Result |
|---|---|
| Korean tech explainer, full 15:05 → English, Japanese, Chinese | 366 / 369 lines passed Gemini's listening check |
| NASA *Houston We Have a Podcast* (two hosts), 3 min → Hindi, Tamil, Spanish | 124 / 129 passed · 9 min 7 s on Cloud Run |
| NASA *Curious Universe* (a man and a woman), 3 min → Hindi, Spanish | 88 / 90 passed · male and female voices cast automatically |
| Independent check: Chirp 3 transcribes each dubbed line back (median character error) | Hindi 6.9 % · Tamil 7.0 % · Spanish 0.0 % |
| Line-end overrun vs the original speech, p95 | ≤ 0.16 s |
| Cost per dubbed minute (model + compute, estimate) | ≈ $0.03 |

`tools/roundtrip_check.py` reproduces the round-trip table (`docs/validation/`). Most residual Hindi/Tamil error is
English names written in native script. Automated checks are not a native-speaker rating.

## Consent

A cloned voice is used only when two locks agree: the video's channel belongs to a creator who recorded a spoken
consent statement, and the diarized speaker verifies against that recording (ECAPA cosine ≥ 0.45; the creator
scores 0.86–0.90, other people ≤ 0.09). Everyone else gets a preset voice that Gemini picks after listening to them.

## Run it

Python 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg.

```bash
uv sync --no-default-groups --group dev
uv run --no-default-groups --group dev pytest        # offline test suite
uv sync --group sep                                  # + demucs/ECAPA for real synthesis
uv run python -m dub.pipeline https://youtu.be/<id> --max-sec 180 --to hi,es
```

Configuration is environment-only (`dub/config.py`): `GEMINI_API_KEY`, `GEMINI_TTS_API_KEY`, `DUB_GCP_PROJECT`,
`DUB_BUCKET`, `DUB_VOICE_ID`, `DUB_CONSENTED_CHANNELS`, `DUB_PROXY`. Paid APIs (Gemini, Chirp, TTS) bill per use.

Deploy: `gcloud builds submit` the Dockerfile → `gcloud run jobs update viberick-dub-worker --image …` and
`gcloud run deploy viberick-dub --image …` → `firebase deploy --only hosting:viberick-dub`.

## Limits

- The public app dubs the first 3 minutes of a video, up to 4 languages per job; source languages are Korean,
  English, Japanese and Chinese.
- Overlapping speech goes to the dominant speaker. Lip sync is not attempted.
- Captions burned into the source video stay in the picture.

## Repository

`dub/` pipeline (one module per step) · `server/` API · `web/` studio · `tests/` · `tools/` validation and
publishing scripts · `deck/` submission deck (`build_v3.py`) · `demo/` submission film (Remotion) ·
`docs/` design notes and validation results.
