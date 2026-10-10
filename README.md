# VibeRick Dub

**One video. Every language. Your own voice.**

Paste a YouTube link. An AI agent transcribes it, translates every sentence to fit its timing, speaks it in
the creator's own cloned voice, then listens back to every line and repairs what doesn't sound right. You get
dubbed audio tracks and subtitles, ready to upload to YouTube's multi-language audio.

- Live app: https://viberick-dub.web.app
- Languages in this version: Korean, English, Japanese, Chinese (Simplified). The source language is detected.
- Team VibeRick, Google Cloud AI Builder Cup 2026, theme: Media, Content & Digital Experiences.

## Why

YouTube reports that creators who add multi-language audio get over 25% of their watch time from viewers in
other languages. Its built-in auto-dubbing does not use the creator's voice, cannot be edited, and for Korean
sources offers only English and Indonesian. Dubbing services that clone the voice charge about $0.33–2.20 per
minute. VibeRick Dub costs about $0.03 per dubbed minute on Google Cloud (measured).

## How it works

```
YouTube URL
  → yt-dlp download (residential proxy fallback on Cloud Run) → demucs: speech / music split
  → Chirp 3: every word with a timestamp + speaker label (diarization)
  → Gemini 3.8 Flash listens and corrects the transcript; corrected text is aligned back onto Chirp's timings
  → sentences (Korean breath fragments merged; never across speakers)
  → voice casting: consent lock + speaker verification → creator's cloned voice; Gemini picks presets for others
  → Gemini writes a dubbing brief (topic, style, term rules)
  → Gemini translates each sentence to a character budget from its time slot and the voice's measured speed
  → Gemini 3.8 Flash TTS voice replication speaks each sentence in the creator's voice
  → agent loop per line: measure → shorten if too long → time-fit → Gemini listens →
       re-synthesize → re-translate → flag for a human
  → placed on the original timeline over the music bed, −14 LUFS → dubbed MP4/M4A + SRT/VTT
```

Every agent action is an event in Firestore, so the web app shows the agent working live.

### Google Cloud and Gemini

| Service | What it does here |
|---|---|
| **Gemini 3.8 Flash** (Vertex AI) | Proofreads the transcript by listening to the audio, writes the dubbing brief, translates to a time budget, shortens/lengthens lines, listens to every dubbed clip and judges it, casts preset voices for other speakers |
| **Gemini 3.8 Flash TTS voice replication** | The creator's own voice in other languages, from a 20 s reference and a spoken consent recording |
| **Chirp 3** (Speech-to-Text v2) | Word timestamps and speaker diarization (the timing backbone; Gemini's own timestamps drift by up to 42 s) |
| **Cloud Run** | API service (FastAPI) and the dubbing worker as a Cloud Run Job (4 vCPU, demucs + ECAPA on CPU) |
| **Firestore** | Jobs, the live agent event stream, and per-line results the UI reads in real time |
| **Firebase Hosting** | The web app; `/api/**` is rewritten to the Cloud Run service |
| **Cloud Storage** | Audio for batch recognition; published dubbed videos, audio and subtitles |
| **Secret Manager / Artifact Registry / Cloud Build** | Keys, the container image, builds |

### Consent, by design

The cloned voice is used only when two locks agree:
1. the video's channel belongs to a creator who recorded the consent statement, and
2. the diarized speaker's voice verifies against that recording (ECAPA speaker embedding, cosine ≥ 0.45;
   measured: the creator 0.90, other people 0.00–0.09).

Every other speaker, and every video from any other channel, gets a Gemini preset voice chosen by Gemini after
listening to that speaker. Only the consenting person's 192-number voice embedding is stored, never their audio.
All generated audio carries Gemini's SynthID watermark.

## Results (measured)

Korean tech explainer (`Fty2sz3dBwU`) dubbed into English, Japanese and Chinese:

| | |
|---|---|
| First 3 min, end to end (download → 3 dubbed videos) | 2 min 52 s · 69 / 69 lines verified by Gemini listening |
| Full 15:05 video | 11 min · 366 / 369 lines verified (3 flagged for review) |
| Timing drift p95 | ≤ 0.16 s |
| Speaker similarity of the English clone to the creator (ECAPA cosine) | 0.68 (other people: 0.00–0.09) |
| Transcript error (CER) vs the creator's edited captions | 7.6–7.9 % (Chirp 3 alone 8.6 %, Gemini alone 10.6–11.8 %) |
| Cost per dubbed minute | ≈ $0.03 (Gemini text $0.009 + TTS $0.014 + Chirp $0.005 + Cloud Run $0.003) |

A 2-minute two-speaker English podcast dubbed into Korean: Chirp separated the speakers, Gemini cast a male
and a female preset, 28 / 28 lines verified, nobody received the cloned voice.

## Run it locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg, and Google credentials (see `dub/config.py`).

```bash
uv sync
uv run pytest                                   # 49 unit tests, no network
uv run python -m dub.pipeline https://youtu.be/<id> --max-sec 180 --to en,ja,zh-Hans
open runs/<id>.180s/review.html                 # video + synced transcript + agent log
```

## Deploy

```bash
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/viberick-dub/app:vN
gcloud run jobs deploy viberick-dub-worker --image ... --command python --args=-m,dub.worker
gcloud run deploy viberick-dub --image ... --allow-unauthenticated
firebase deploy --only hosting:viberick-dub,firestore:rules
```

## Limits

- Public demo dubs the first 3 minutes of a video, 40 jobs a day.
- Overlapping speech is assigned to the dominant speaker.
- Lip sync is not attempted; timing is matched sentence by sentence.

## Code map

`dub/` pipeline (one module per step, `pipeline.py` orchestrates with per-step caching) · `server/app.py` API ·
`dub/worker.py` Cloud Run Job · `web/` Firebase Hosting app · `tests/` unit tests · `docs/plans/` the build plan.
