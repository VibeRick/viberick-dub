# VibeRick Dub — design contract (2026-10-11)

Applies to the web app, the demo film and the deck, so all three read as one product.
Before-files: `index.before.html`, `style.before.css`, `app.before.js` in this folder.

## Register
- Landing: Editorial carried by the real product (the hero is a working player, not an illustration).
- Studio: Instrument. Borders and background steps, one accent for interactive/live.
  ↳ art-direction-first registers.md: Linear 4 z-layers, 28 blurs; Toss sticky + blur, no scroll library (measured 2026-09-06).

## Hero artifact
The dub itself: one video, a rail of languages (original + EN/JA/ZH), switching keeps the playback
position and the speaker's own voice. Replace the sample with the Jaeho × Yuke two-shot when recorded.

## Tokens
- Ground `#0c0c0d`, steps `#141416` / `#1b1b1e` / `#242428`, hairline `rgba(255,255,255,.08)`.
- Ink `#f3f1ec` / `#b4b1aa` / `#7d7a74`. Accent (interactive, live, agent) `#ff6a2b`. Pass `#6fd3a0`, flag `#ffb547`.
- Speakers `#8ec5ff`, `#f5c26b`, `#b7a4ff`, `#7fe0c4` (never the accent).
- Committed dark ground on every surface (screening room: video is the content).

## Type
- Display Inter Tight 600, Latin tracking −0.03 to −0.04em, leading 0.94–1.05.
  ↳ Latin display −0.02 to −0.06em: Vercel −0.06, Linear −0.022 (corpus, 2026-09-06).
- Hangul: Pretendard Variable, tracking `normal`. Japanese Noto Sans JP, Chinese Noto Sans SC.
  ↳ 7 of 10 KR sites `normal`; floor −0.033em kakaocorp (2026-09-06).
- UI Inter 15px/1.6. Mono JetBrains Mono for timecodes, eyebrows, section numbers; tabular numerals.

## Depth & motion
- z-layers: 0 ground · 1 content · 2 sticky bar (blur 14px). No card shadows.
- One curve `cubic-bezier(.25,.46,.45,.94)`; state 0.15s; no scroll reveals. Reduced-motion path in CSS.
  ↳ Linear one curve ×438, 0.1s ×212 (2026-09-06).

## Copy rules
- Say what it does, confidently; numbers carry their scope in one clause ("on the full 15-minute video").
- No hedging paragraphs in the UI. Limits live in README and the deck's limits slide.
