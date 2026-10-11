# VibeRick Dub — submission film v2 (target 2:45, hard cap 2:58)

Narration: Jaeho's consented cloned voice (Gemini TTS replication), English.
Footage: Jaeho's own video (caption-free master), a live Cloud Run job on the redesigned studio,
and a short attributed excerpt of Google DeepMind: The Podcast (preset voices; nobody is cloned
without consent). Design tokens = docs/redesign-2026-10-11/DESIGN.md.

| # | t | picture | sound |
|---|---|---|---|
| 1 | 0:00–0:14 | Cold open. Jaeho's video, one sentence, hard cuts KO → EN → JA → ZH; big language label, his face. | Original/dub audio only. |
| 2 | 0:14–0:32 | Title "Your voice. Every language." → problem line. | N1 |
| 3 | 0:32–0:58 | Live capture: paste link, pick languages, studio streams the agent (sped up, timecode shown). | N2 |
| 4 | 0:58–1:24 | DeepMind podcast, two speakers → Korean / Japanese, speaker colours, casting reasons on screen. | N3, then the exchange unnarrated |
| 5 | 1:24–1:48 | Self-repair: real event rows for zh #15 ("WhyBrick" → re-speak → pass) and ja #13 (wrong language → pass). | N4 |
| 6 | 1:48–2:02 | Line edit: change a line, preview, accept. | N5 |
| 7 | 2:02–2:30 | Architecture, built up node by node; numbers. | N6 |
| 8 | 2:30–2:45 | Consent + close, URL. | N7 |

## Narration (English)

N1 — I make videos in Korean. That was me in English, Japanese and Chinese. I never recorded those lines. VibeRick Dub did, in my own voice, from one YouTube link. Reaching a new audience used to mean translators, voice actors, re-timing and subtitles, for every language.

N2 — Paste a link and choose languages. A Cloud Run job starts, and you watch the agent work. Chirp 3 timestamps every word and tells the speakers apart. Gemini listens to the audio, fixes the transcript, and translates each sentence to fit the time it was spoken.

N3 — It handles conversations too. Here is Google DeepMind's podcast. Gemini listens to each speaker and casts a matching voice. Nobody's voice is cloned without consent.

N4 — Then every line is checked by ear. Gemini listens to each clip: right language, every word, right length. Here it heard my company's name come out as "WhyBrick". The agent spoke the line again, listened again, and it passed. Whatever it can't fix, it flags for a human.

N5 — And you stay in control. Here the agent dropped the show's name from a Korean line. I add it back, preview just that line in the same voice, Gemini checks it again, and I accept.

N6 — It is all Google Cloud. Firebase hosts the studio. Cloud Run starts one job per dub, so it scales with creators and costs nothing when idle. Every agent decision streams through Firestore, and the media lands in Cloud Storage. On a full fifteen-minute video, three hundred sixty-six of three hundred sixty-nine lines passed the listening check, at about three cents per dubbed minute.

N7 — My voice is only used because I recorded my consent, and my voice matches it. You made the video. We'll handle the languages.

On-screen attribution for scene 4: "Excerpt: Google DeepMind: The Podcast — 'The future of intelligence' (youtu.be/PqVbypvxDto). Dubbed with preset voices for demonstration."
