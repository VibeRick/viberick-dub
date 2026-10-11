# Outcome-first launch direction — 2026-10-11

This is the next production brief; the existing 28-second StudioDemo remains the current preview until the replacement is verified. Earlier 24/72-second notes below are historical.

Message: **You made the video. We’ll handle the languages.**
Supporting promise: multilingual audio and subtitles, with timing-aware translation and automatic audio checks. Consented creator cloning is the second proof. Human editing is optional, not the headline task.

Deliverables: a 35–45-second product cut and a roughly 2:20 English hackathon film. Reuse actual product UI and actual output; do not simulate a successful generation or claim processing time from sped-up editing.

Opening proof: play a complete creator source sentence, then its English and Japanese output with exclusive audio and matching captions. Fit duration to the actual complete utterances rather than forcing a 4-second cut. “I only recorded it once” means the source was recorded once; it must not imply every generated take was first-pass successful. Keep creator proof separate from the user's two-speaker podcast demonstration. Do not replace the requested podcast story with a creator tutorial without an explicit content decision.

Submission story:
1. Hear the multilingual result immediately.
2. Show URL → languages → actual processing → finished versions.
3. Hear a two-speaker exchange; show the selected language's captions and actual speech timing.
4. Reveal a real automatic failure/repair with archived evidence labelled as recorded.
5. Show optional edit control briefly, then downloadable video/audio/subtitles.
6. Explain Gemini/Chirp and Cloud Run/Firestore/Firebase with one concise architecture view.
7. Close on measured results and the exact public working link.

Capture plan: full-size product at desktop width; intentional closeups on language change, playback, quality status and downloads. One focal action at a time. Music absent or substantially reduced during voice comparisons. Use actual UI terminology. Keep disclosures legible without covering the main result. A representative sample must have confirmed submission/reuse rights.

References reviewed: https://github.com/EveryInc/product-launch-video (storyboard and real-UI discipline), https://www.skills.sh/heygen-com/hyperframes/product-launch-video (capture-to-storyboard sequence), https://www.remotion.dev/docs/ai/skills (implementation), https://screen.studio/create/product-demo-videos (recording presentation). Existing Remotion engine retained; no new external skill installed.

## English submission narration — draft for production

This narration accompanies real product captures and prerecorded output examples. Target total film duration: 2:10–2:35 including 25–35 seconds of uninterrupted demonstration audio. Do not read stage directions aloud.

**Problem / 0:00–0:12**
You made a video worth sharing. Reaching another language means translating the script, recording voices, matching the timing and building subtitles. Then doing it all again.

**Product / 0:12–0:30**
VibeRick Dub handles that workflow. Paste your video link and choose your languages. It produces dubbed video, audio tracks and subtitles you can download and use.

**Output proof / 0:30–0:55**
Here is the same conversation in another language. The speakers stay distinct, and subtitles follow the generated speech.
[Play complete original and dubbed speaker turns; no narration or music over the comparison. The selected interview is transcript-assisted and uses presets; disclose this on screen.]

**What makes it work / 0:55–1:20**
A translation is not finished when the words are correct. It also has to fit the time a speaker actually talks. Chirp supplies word timestamps. Gemini translates for those windows. We measure the generated audio, adjust the wording or pace, and check what the audio actually says.

**Automatic repair / 1:20–1:35**
In this recorded run, the checker caught a Japanese line spoken in Korean. The pipeline generated another take. Unresolved problems are flagged, and you can preview an exact-wording edit before accepting it.
[Show the actual archived failure and recovery, labelled as a separate recorded run.]

**Creator voice / 1:35–1:55**
And when the creator consents, it can use their own voice. This is my original recording, followed by the generated version.
[Play complete source/dub pair. Keep separate from the preset-voice interview.]

**Architecture and finish / 1:55–2:20**
Firebase hosts the studio. Firestore carries progress. Cloud Run executes the API and workers, with media in Cloud Storage. Four pipeline languages are tested; model checks are not a substitute for human quality evaluation. Switch languages, download your versions, and share them where your audience watches.

You made the video. We’ll handle the languages.

Production dependencies: current product captures, representative interview reuse permission or replacement, final narration take, measured duration and full audio/video review. This draft makes no quantified labor savings, blanket YouTube-quality superiority or lip-sync claim.

---

Current primary revision: 24-second simultaneous Source → Gemini → KO/JA/ZH comparison. Six complete short utterances, with 0.8-second focus changes. See short-edit-manifest.json. The following longer edit is archived as PodcastLongDraft.

# Current podcast demo edit

## Story

The first frame identifies the product category: **AI AUDIO DUBBING**. Recognizable real interview footage establishes the source; the audience then hears the same complete exchange in four languages. Speaker identity stays clear through distinct presets, names and persistent colors. Actual source timing and rendered speech intervals provide evidence without a simulated processing screen.

1. 3 s: Category and actual portraits.
2. Original English opening exchange, complete (source 0–11.45 s).
3. Korean version of that exchange, complete.
4. Japanese version, complete.
5. Chinese version, complete.
6. Complete later Demis answer in Korean (source 21.84–40 s; rendered end 39.906 s).
7. 7 s: Actual studio capture and readable product URL.

The source contains turn overlap after 13.4 seconds. The opening comparison deliberately ends at the complete first pair, before the next sentence begins, to avoid a truncated sentence. The later Korean answer was verified not to include an unfinished preceding speaker.

## Evidence and limits

- Eighteen target rows passed the automatic listening checks in the recorded run; this is not human listening certification.
- A separate Korean opening terminology edit was generated and checked after the initial run.
- Charon and Algieba are presets, not speaker clones.
- Source alignment is transcript-assisted, not a measured end-to-end diarization result.
- The 48.19-second run metric excludes downloading and the later editorial repair; it is not advertised as deployed API latency.
- The video is a local preview. The product URL is real; the screenshot describes the current local revision.
- No fabricated clicks, processing events or accepting-an-edit recording is included.

The old creator experiment and its three-minute RMS comparison remain archived evidence and are clearly separated in the review deck.
