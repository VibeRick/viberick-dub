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
| 4 | 0:58–1:24 | DeepMind podcast, two speakers → Hindi, speaker colours, casting reasons on screen. | N3, then the exchange unnarrated |
| 5 | 1:24–1:48 | Self-repair: real event rows for zh #15 ("WhyBrick" → re-speak → pass) and ja #13 (wrong language → pass). | N4 |
| 6 | 1:48–2:02 | Line edit: change a line, preview, accept. | N5 |
| 7 | 2:02–2:30 | Architecture, built up node by node; numbers. | N6 |
| 8 | 2:30–2:45 | Consent + close, URL. | N7 |

## Narration (English)

N1 — I make videos in Korean. That was me in English, Hindi and Chinese. I never recorded those lines. VibeRick Dub did, in my own voice, from one YouTube link. Creators who add dubbed audio already get over a quarter of their watch time from other languages. But today that means translators, voice actors, re-timing and subtitles, for every language.

N1b — YouTube's own auto-dubbing takes a Korean video only into English or Indonesian, and you can't edit it. So I built VibeRick Dub.

N2 — Paste a link and choose up to four of a hundred and twenty-five languages. A Cloud Run job starts, and you watch the agent work. Google's Chirp 3 speech model timestamps every word and tells the speakers apart. Gemini is multimodal, so it listens to the audio itself, fixes the transcript, and translates each sentence to fit the time it was spoken.

N3 — It handles conversations too. Here is Google DeepMind's podcast, dubbed into Hindi. Gemini listens to each speaker and gives each one a matching voice. Nobody's voice is cloned without consent.

N4 — But how do you know a dub is right? Gemini listens to every line the agent made: the right language, every word, the right length. Here it heard my company's name come out as "WhyBrick". The agent spoke the line again, listened again, and it was fixed. Whatever it can't fix, it flags for a human.

N5 — And you stay in control of each line. Here the agent dropped the show's name from a Korean line. I add it back and preview just that line in the same voice. Gemini checks it again, and I accept. Only that line is regenerated; the rest of the dub stays as it was.

N6 — It is all Google Cloud. Firebase hosts the studio. Cloud Run starts one job per dub, so it scales with creators and costs nothing when idle. Every agent decision streams through Firestore, and the media lands in Cloud Storage. On a full fifteen-minute video, three hundred sixty-six of three hundred sixty-nine lines passed the listening check, at about three cents per dubbed minute.

N7 — Any video. A hundred and twenty-five languages. Your own voice. You make the video. VibeRick Dub takes it to the world.

On-screen attribution for scene 4: "Excerpt: Google DeepMind: The Podcast — 'The future of intelligence' (youtu.be/PqVbypvxDto). Dubbed with preset voices for demonstration."
