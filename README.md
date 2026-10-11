# VibeRick Dub

**You made the video. We’ll handle the languages.**

VibeRick Dub turns a YouTube video into reviewable dubbed tracks and subtitles. It combines timestamped transcription, timing-aware translation, consent-gated voice replication and automatic listening checks. The default workflow delivers language versions to play and download; optional line edits let creators preview and accept a replacement without rebuilding every track.

- Deployed app: https://viberick-dub.web.app
- Supported pipeline languages: Korean, English, Japanese and Chinese (Simplified).
- Team VibeRick · Google Cloud AI Builder Cup 2026 · Media, Content & Digital Experiences.

## Current demo: AI audio dubbing

The current editable demo is `demo/remotion/`, composition **VibeRickDubPodcast**: a real Lex Fridman / Demis Hassabis interview excerpt dubbed into Korean, Japanese and Chinese with distinct **preset** voices (Charon / Algieba). Source turns are transcript-assisted, not an automatic diarization benchmark. The completed podcast run has 18/18 automatic passes; the earlier creator recording and its silence comparison are separate evidence. The old creator demo remains archived and is not the current submission film. See `demo/remotion/demo.md` for the exact edit and limitations.

## Revision status — 2026-10-11

The revised studio, API and worker are deployed. API revision `viberick-dub-00010-rih` serves 100% of traffic. Real cloud checks verified job creation, idempotency, ownership rejection, public media, preview acceptance/discard and verbatim manual edits. The full local suite passed 167 tests; native listening review and the new public podcast sample remain pending. Deployment evidence and rollback are in `docs/review-2026-10-10/deployment-readiness.md`. The historical results below remain separately labelled.

The studio shows per-language progress, named speakers and actual output timing. A line can be edited, generated as a preview, then accepted or discarded; revision checks protect against stale edits. Manual edits preserve the submitted words and flag timing or content problems. Normal automatic dubbing retains measured rewriting and verification. The pipeline records rendered audio positions for subtitles and protects speaker/scene boundaries.

Burned-in source captions are part of the video pixels. Turning translated subtitles off does not remove them. Use a caption-free source master for a clean demonstration, or show translated subtitles separately. The original creator's edited captions are useful reference material, but not a verbatim transcription ground truth.

## Why

Creators need to hear whether a translation fits the delivery, preserves the meaning and sounds natural. Our focus is an inspectable dubbing workflow: listen, find a problem, preview a replacement and accept the better take. Supported language coverage and measured quality matter more than a provider's maximum language count.

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
listening to that speaker. Speaker verification stores a 192-number embedding. This is not an audio-retention guarantee: voice replication uses provider-side voice state, and local reference/consent recordings and generated audio also exist. Retention and deletion need to cover each of those locations. A similarity threshold is a technical gate, not independent proof of identity or permission. Existing consent/channel configuration must be reviewed before enrolling anyone else.

## Recorded baseline results

Korean tech explainer (`Fty2sz3dBwU`) dubbed into English, Japanese and Chinese:

| | |
|---|---|
| First 3 min, end to end (download → 3 dubbed videos) | 2 min 52 s · 69 / 69 automatic listening checks passed |
| Full 15:05 video | 11 min · 366 / 369 automatic checks passed (3 flagged) |
| Positive end overrun p95 | ≤ 0.16 s; not absolute timing error or proof of natural pacing |
| Speaker similarity of the English clone to the creator (ECAPA cosine) | 0.68 (other people: 0.00–0.09) |
| Transcript error (CER) vs the creator's edited captions | 7.6–7.9 % (Chirp 3 alone 8.6 %, Gemini alone 10.6–11.8 %) |
| Illustrative cost per dubbed minute | ~ $0.03: recorded text usage priced at configured rates, plus estimated TTS, STT and compute. Not a reconciled bill; excludes some storage/proxy/download costs and new revisions. |

A 2-minute two-speaker English podcast dubbed into Korean: Chirp separated the speakers, Gemini cast a male
and a female preset, 28 / 28 automatic checks passed, nobody received the cloned voice.

Automatic passes do not certify translation accuracy or voice quality. The full-length baseline has excessive sentence-end silence and occasional wrong-language speech. Fresh generation, comparison against source speech and native listening review are required before claiming those gaps are solved.

## Run it locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg, and Google credentials (see `dub/config.py`).

```bash
uv sync --no-default-groups --group dev           # lightweight offline tests
uv run --no-default-groups --group dev pytest                                   # offline suite; count changes with development
# Full synthesis additionally requires: uv sync --group sep
uv run python -m dub.pipeline https://youtu.be/<id> --max-sec 180 --to en,ja,zh-Hans
open runs/<id>.180s/review.html                 # video + synced transcript + agent log
```

Set `GEMINI_API_KEY` and `GEMINI_TTS_API_KEY` explicitly using your approved secret manager or process environment; the application does not search Keychain. Set `DUB_GCP_PROJECT`, `DUB_GCP_ACCOUNT`, `DUB_BUCKET`, `DUB_RUNS`, and `DUB_VOICE_ID` for your deployment. Creator voice use additionally requires `DUB_CONSENTED_CHANNELS` and matching consent evidence. Runtime defaults name the original VibeRick deployment; replace them when reproducing in another project. Use only this project's configured Google accounts and credentials. Text, speech recognition and voice generation can bill separately; obtain a generation budget before running a new job.

## Deployment scope

Firebase serves the UI; Cloud Run hosts the API and worker, with Firestore for progress and Cloud Storage for media. The service/worker are configured in Seoul, but **not all processing is Seoul-only**: Chirp is configured in the US and Gemini/voice services have separate endpoint and project configuration. Do not promise regional data residency from the Cloud Run region alone.

## Offline verification and source handoff

The non-live tests construct their own small fixtures; private recordings and paid API calls are not required. Install ffmpeg and Node.js so audio and browser-helper tests run. The production separation/verification models are needed for synthesis, not the lightweight test lane.

`python tools/build_source_release.py` creates a local, allowlisted source ZIP and SHA256 manifest under `runs/source-release/`. It excludes run data, voice recordings, media, ownership state, operational documents and Git history. It does not publish anything. The presentation and editable film assets are separate delivery artifacts.

## Deploy

```bash
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/viberick-dub/app:vN
gcloud run jobs deploy viberick-dub-worker --image ... --command python --args=-m,dub.worker \
  --cpu 4 --memory 8Gi --task-timeout 3600 --max-retries 0
gcloud run deploy viberick-dub --image ... --allow-unauthenticated
firebase deploy --only hosting:viberick-dub,firestore:rules --project viberick --account jaeho.shin@viberick.com
```

## Limits

- Public demo dubs the first 3 minutes of a video, 40 jobs a day. Outputs of public jobs are deleted after 7 days;
  only the showcase examples stay. Verify the deployed lifecycle policy before relying on deletion.
- Overlapping speech is assigned to the dominant speaker.
- Lip sync is not attempted; timing is matched sentence by sentence.

## Code map

`dub/` pipeline (one module per step, `pipeline.py` orchestrates with per-step caching) · `server/app.py` API ·
`dub/worker.py` Cloud Run Job · `web/` Firebase Hosting app · `tests/` unit tests · `docs/plans/` the build plan.

## Submission artifacts

The original deck and demo remain preserved. The latest outcome-first deck is a review draft at `deck/outcome-review-2026-10-11/VibeRick-Dub-outcome.pdf` (editable PPTX alongside). The prior review deck remains preserved. Public repository publication, a final demo URL and submission form delivery remain pending. The app deployment and cloud edit workflow are verified; the new podcast film and sample are available for local review.

Build an isolated review deck without overwriting the original:

```bash
DUB_DECK_RUN=Fty2sz3dBwU.180s DUB_DECK_OUTPUT=deck/review-2026-10-10/VibeRick-Dub-review.pptx uv run --with python-pptx python deck/build.py
# equivalent: --run Fty2sz3dBwU.180s --output deck/review-2026-10-10/VibeRick-Dub-review.pptx
```
