Current primary revision: **28-second audio studio demo**. Real interview footage, simultaneous KO/JA/ZH subtitles, speaker order and measured timestamp lanes fill one workspace. Gemini TTS model coverage is labelled 130+; app validation is labelled 4 languages. Creator cloning is described separately from podcast preset casting. See studio-edit-manifest.json.

# VibeRick Dub · AI AUDIO DUBBING

Current editable preview: **http://localhost:8891/VibeRickDubPodcast**

The primary demo uses the real Lex Fridman / Demis Hassabis interview, with two distinct AI preset voices. Charon portrays Lex; Algieba portrays Demis. The demo does not clone either speaker. Source: [Lex Fridman Podcast #475](https://www.youtube.com/watch?v=-HzgcbRXUK8), 56:27–57:07.

## Current edit

Previous diagram revision: **24 seconds · 1920×1080 · 30 fps**. Source → Gemini → Korean/Japanese/Chinese appear simultaneously. Each target language plays one short Lex utterance and one short Demis reply, with a 0.8-second highlight transition. The previous 72.63-second film is preserved as `PodcastLongDraft`.

Previous longer edit: 72.63 seconds · 1920×1080 · 30 fps. The first frame says **AI AUDIO DUBBING** over actual stills of both speakers. The film plays the complete opening exchange in original English, Korean, Japanese and Chinese, one audible track at a time. It then plays the complete later Korean answer and shows the actual studio with its product URL.

Lex uses amber; Demis uses blue. Translated text is shown with the English source; the long answer uses an explicitly labeled English gloss. Speech bars use recorded output intervals. Each clip ends after its complete utterance plus 0.35 seconds, with no fixed silent padding. Source turns were aligned from audio against the published transcript; this selected demo is not an automatic diarization benchmark.

The source media remains separate from the H264 browser preview copy, with separate SHA256 values in the generated manifest. The studio capture is an actual medium viewport (889×1341) and retains its aspect ratio. The current Korean opening uses the reviewed wording “새로운 가설이나 과학적 발견이라니, 정말 멋진 기분이겠죠.”

The previous creator-video composition is retained under **Archive** in Studio. Its three-minute quality comparison is separate evidence, not a result from this podcast.

## Reproduce locally

```sh
npm ci
python3 scripts/prepare-podcast.py
npm run dev -- --no-open --port=8891
npm run lint
```

Requires the local `runs/podcast-demo-2026-10-11` artifacts and `docs/review-2026-10-10/podcast-studio.jpg`. Generated media and manifests are ignored by Git. Preparation snapshots completed files; it makes no AI calls and leaves source artifacts unchanged.

No final MP4 export, upload or publication has been performed. This remains a local review preview. Final media publication and permissions need to be settled before public use.
