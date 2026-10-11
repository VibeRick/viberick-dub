# VibeRick Dub film

The under-3-minute submission film, built with [Remotion](https://www.remotion.dev/).

- Composition: `VibeRickDubFilm` (`src/film/Film.tsx`); one `Film-<scene>` composition per scene for previews.
- Script and narration text: `../film/SCRIPT.md`. Narration is generated in the creator's consented voice by `../film/narrate.py`.
- Footage timings, speaker casting and on-screen text: `src/film/footage.json`.
- Media in `public/film/` (dubbed clips, narration WAVs, screen recordings) is not committed; it comes from real VibeRick Dub jobs.

```bash
npm ci
npx remotion studio                                   # preview
npx remotion render VibeRickDubFilm out/film.mp4      # render
```
