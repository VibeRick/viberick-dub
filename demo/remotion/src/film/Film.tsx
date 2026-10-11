// VibeRick Dub — submission film v2. Script: demo/film/SCRIPT.md. Tokens: docs/redesign-2026-10-11/DESIGN.md.
import { Audio, Video } from "@remotion/media";
import React from "react";
import {
  AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing,
} from "remotion";
import N from "../film-narration.json";
import footage from "./footage.json";
import OPEN_TAKES from "./open.json";

type Clip = { at: number; dur: number; trim: number; rate: number; label?: string; zoom?: number[] };
type Take = { l: string; lang: string; label: string; file: string; start: number; end: number };
type Footage = {
  liveFile: string; liveTotal: number; live: Clip[]; liveCallouts: { at: number; x: number; y: number; title: string; body?: string }[];
  editFile: string; editTotal: number; edit: Clip[]; repair: { start: number; end: number };
  podcast: { attribution: string; cast: { spk: string; name: string; voice: string; why: string }[];
    turns: { spk: string; start: number; end: number; text: Record<string, string> }[]; takes: Take[] };
};
const F = footage as unknown as Footage;

export const FPS = 30;
const C = {
  ground: "#0c0c0d", s1: "#141416", s2: "#1b1b1e", s3: "#242428", line: "rgba(255,255,255,.10)",
  ink: "#f3f1ec", ink2: "#b4b1aa", ink3: "#7d7a74", accent: "#ff6a2b", pass: "#6fd3a0", flag: "#ffb547",
  spk0: "#8ec5ff", spk1: "#f5c26b",
};
const display = "'Inter Tight', 'Pretendard Variable', sans-serif";
const ui = "Inter, 'Pretendard Variable', 'Noto Sans JP', 'Noto Sans SC', sans-serif";
const mono = "'JetBrains Mono', ui-monospace, monospace";
const ease = Easing.bezier(.25, .46, .45, .94);
const sec = (s: number) => Math.round(s * FPS);

const FontFaces = () => (
  <style>{`
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+JP:wght@500;700&family=Noto+Sans+SC:wght@500;700&display=block');
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');
`}</style>
);

const fadeIn = (f: number, start = 0, len = 9) => interpolate(f, [start, start + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
const rise = (f: number, start = 0, len = 12) => interpolate(f, [start, start + len], [18, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.ink3 }) => (
  <div style={{ font: `500 22px ${mono}`, letterSpacing: ".1em", textTransform: "uppercase", color }}>{children}</div>
);

const Brand: React.FC<{ opacity?: number }> = ({ opacity = 1 }) => (
  <div style={{ position: "absolute", left: 72, top: 56, display: "flex", alignItems: "center", gap: 14, opacity, font: `500 26px ${ui}`, color: C.ink }}>
    <Img src={staticFile("film/logo.png")} style={{ width: 36, height: 36, borderRadius: 8 }} />
    <span>VibeRick <b style={{ fontWeight: 700 }}>Dub</b></span>
  </div>
);

// ── 1 · cold open: one sentence, four languages, same face and voice ────────────────────────
const OPEN = [
  { l: "orig", lang: "ko", label: "한국어", tag: "ORIGINAL", start: 8.88, end: 12.84, text: "제 부모님만 하더라도 이제 다 ChatGPT한테 물어보시는 것 같아요." },
  { l: "en", lang: "en", label: "English", tag: "AI DUB · HIS OWN VOICE", start: 9.0, end: 12.8, text: "Even my parents seem to ask ChatGPT about everything these days." },
  { l: "hi", lang: "hi", label: "हिन्दी", tag: "AI DUB · HIS OWN VOICE", start: 8.53, end: 11.82, text: "लगता है मेरे माता-पिता भी अब सब ChatGPT से ही पूछते हैं।" },
  { l: "zh-Hans", lang: "zh-Hans", label: "中文", tag: "AI DUB · HIS OWN VOICE", start: 8.53, end: 12.62, text: "拿我父母来说，现在好像全都会去问ChatGPT了。" },
];
const OPEN_PAD = 0.35;
// Dubbed shots play a fresh, unstretched take (demo/film/coldopen.py) over the original bed.
const takeSec = (o: typeof OPEN[number]) => (OPEN_TAKES as Record<string, number>)[o.l];
export const openDur = (o: typeof OPEN[number]) => sec((takeSec(o) ?? o.end - o.start) + OPEN_PAD * 2);
const coldOpenFrames = OPEN.reduce((n, o) => n + openDur(o), 0);

const Face: React.FC<{ src: string; trim: number }> = ({ src, trim }) => {
  // The facecam sits at x1664 y824, 224 px square in the 1920×1080 master.
  const size = 620, s = size / 224;
  return (
    <div style={{ width: size, height: size, borderRadius: "50%", overflow: "hidden", position: "relative", boxShadow: `0 0 0 2px ${C.line}` }}>
      <Video src={src} trimBefore={trim} muted style={{ position: "absolute", width: 1920 * s, height: 1080 * s, left: -1664 * s, top: -824 * s, maxWidth: "none" }} />
    </div>
  );
};

const ColdOpenShot: React.FC<{ o: typeof OPEN[number]; i: number }> = ({ o, i }) => {
  const f = useCurrentFrame();
  const src = staticFile("film/solo.orig.mp4");
  const trim = sec(o.start - OPEN_PAD);
  const audio = takeSec(o) ? <Audio src={staticFile(`film/open.${o.l}.wav`)} /> : <Audio src={src} trimBefore={trim} />;
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <Video src={src} trimBefore={trim} muted style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", filter: "blur(28px) brightness(.32) saturate(.8)", transform: "scale(1.1)" }} />
      {audio}
      <AbsoluteFill style={{ flexDirection: "row", alignItems: "center", padding: "0 120px", gap: 96 }}>
        <Face src={src} trim={trim} />
        <div style={{ flex: 1 }}>
          <Eyebrow color={o.l === "orig" ? C.ink3 : C.accent}>{o.tag}</Eyebrow>
          <div lang={o.lang} style={{ font: `600 168px/1 ${display}`, letterSpacing: o.lang === "en" ? "-.04em" : "normal", color: C.ink, marginTop: 18, lineHeight: o.lang === "hi" ? 1.25 : 1 }}>{o.label}</div>
          <div lang={o.lang} style={{ font: `500 44px/1.4 ${ui}`, color: C.ink2, marginTop: 36, maxWidth: 820 }}>“{o.text}”</div>
        </div>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 120, right: 120, bottom: 72, display: "flex", gap: 14 }}>
        {OPEN.map((x, j) => <div key={x.l} style={{ flex: 1, height: 4, borderRadius: 2, background: j < i ? C.ink3 : j === i ? C.accent : C.s3 }} />)}
      </div>
      <Brand opacity={fadeIn(f, 0, 6)} />
    </AbsoluteFill>
  );
};

const ColdOpen = () => {
  let at = 0;
  return <>{OPEN.map((o, i) => { const from = at; at += openDur(o); return <Sequence key={o.l} from={from} durationInFrames={openDur(o)}><ColdOpenShot o={o} i={i} /></Sequence>; })}</>;
};

// ── 2b · YouTube auto-dubbing vs VibeRick Dub (support.google.com/youtube/answer/15569972, 2026-10-11) ─
const COMPARE = [
  ["From a Korean video", "English, Indonesian", "125 languages"],
  ["Whose voice", "a synthetic voice", "your own, with consent"],
  ["Fix a line", "“You cannot edit automatic dubs”", "edit and re-speak each line"],
  ["Checks itself", "—", "Gemini listens to every line"],
];
const Compare: React.FC<{ f: number; at: number; until: number }> = ({ f, at, until }) => (
  <AbsoluteFill style={{ justifyContent: "center", padding: "0 160px", opacity: Math.min(fadeIn(f, at, 8), 1 - fadeIn(f, until - 6, 6)) }}>
    <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.45fr 1.2fr", font: `500 38px ${ui}` }}>
      <span />
      <span style={{ font: `500 26px ${mono}`, color: C.ink3, letterSpacing: ".08em", paddingBottom: 22 }}>YOUTUBE AUTO-DUBBING</span>
      <span style={{ font: `500 26px ${mono}`, color: C.accent, letterSpacing: ".08em", paddingBottom: 22 }}>VIBERICK DUB</span>
      {COMPARE.map(([k, a, b], i) => (
        <React.Fragment key={k}>
          {[k, a, b].map((x, j) => (
            <span key={j} style={{ padding: "26px 0", borderTop: `1px solid ${C.line}`, color: j === 0 ? C.ink3 : j === 1 ? C.ink2 : C.ink, fontWeight: j === 2 ? 600 : 500, opacity: fadeIn(f, at + 6 + i * 7) }}>{x}</span>
          ))}
        </React.Fragment>
      ))}
    </div>
    <div style={{ font: `400 22px ${ui}`, color: C.ink3, marginTop: 30, opacity: fadeIn(f, at + 30) }}>YouTube Help, “Automatic dubbing”, checked Oct 2026</div>
  </AbsoluteFill>
);

// ── 2 · title + problem ─────────────────────────────────────────────────────────────────────
const Title = () => {
  const f = useCurrentFrame();
  const out = sec(11.0);
  const steps = ["Translate the script", "Hire voice actors", "Re-time every line", "Build subtitles"];
  const bridge = sec(N.N1 + .4), named = bridge + sec(6.7);
  return (
    <AbsoluteFill style={{ background: C.ground, color: C.ink }}>
      <Audio src={staticFile("film/N1.wav")} />
      <Sequence from={bridge}><Audio src={staticFile("film/N1b.wav")} /></Sequence>
      <Compare f={f} at={bridge} until={named} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", opacity: fadeIn(f, named, 8) }}>
        <Img src={staticFile("film/logo.png")} style={{ width: 96, height: 96, borderRadius: 20 }} />
        <div style={{ font: `600 150px/.95 ${display}`, letterSpacing: "-.045em", marginTop: 36, transform: `translateY(${rise(f, named)}px)` }}>VibeRick Dub</div>
        <div style={{ font: `500 40px ${ui}`, color: C.ink2, marginTop: 30, opacity: fadeIn(f, named + 10) }}>AI dubbing in your own voice · timed to every sentence · <span style={{ color: C.accent }}>125 languages</span></div>
      </AbsoluteFill>
      <Brand />
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 160px", opacity: interpolate(f, [out, out + 8], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        <Eyebrow>AI dubbing agent · built on Google Cloud</Eyebrow>
        <div style={{ font: `600 196px/.92 ${display}`, letterSpacing: "-.045em", marginTop: 28, opacity: fadeIn(f, 4), transform: `translateY(${rise(f, 4)}px)` }}>Your voice.<br />Every language.</div>
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 160px", opacity: Math.min(fadeIn(f, out + 6), 1 - fadeIn(f, bridge - 8, 8)) }}>
        <Eyebrow>Today, for every language</Eyebrow>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20, marginTop: 36 }}>
          {steps.map((s, i) => {
            const at = out + sec(3.4) + i * sec(.8);
            return <div key={s} style={{ padding: "34px 40px", borderRadius: 18, background: C.s1, border: `1px solid ${C.line}`, font: `600 58px ${display}`, letterSpacing: "-.025em", opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)` }}>
              <span style={{ font: `500 24px ${mono}`, color: C.accent, marginRight: 22 }}>0{i + 1}</span>{s}</div>;
          })}
        </div>
        <div style={{ marginTop: 40, font: `500 34px ${ui}`, color: C.ink2, opacity: fadeIn(f, out + sec(6.8)) }}>× every language you want to reach.</div>
        <div style={{ marginTop: 28, display: "flex", alignItems: "baseline", gap: 24, opacity: fadeIn(f, out + sec(.6)) }}>
          <span style={{ font: `600 64px ${display}`, color: C.accent, letterSpacing: "-.03em" }}>25%+</span>
          <span style={{ font: `400 28px ${ui}`, color: C.ink2 }}>of watch time comes from other languages for creators who add multi-language audio · YouTube, Sep 2025</span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── shared: a screen capture in a window frame ──────────────────────────────────────────────
const Screen: React.FC<{ src: string; trim?: number; rate?: number; label?: string; zoom?: [number, number, number, number]; children?: React.ReactNode }> = ({ src, trim = 0, rate = 1, label, zoom, children }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const z = zoom ? interpolate(f, [0, durationInFrames], [zoom[0], zoom[1]], { easing: ease }) : 1;
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <div style={{ position: "absolute", left: 120, top: 110, width: 1680, height: 945, borderRadius: 18, overflow: "hidden", border: `1px solid ${C.line}`, boxShadow: "0 40px 120px rgba(0,0,0,.6)" }}>
        <div style={{ width: "100%", height: "100%", transform: `scale(${z})`, transformOrigin: zoom ? `${zoom[2]}% ${zoom[3]}%` : "50% 50%" }}>
          <Video src={src} trimBefore={trim} playbackRate={rate} muted style={{ width: "100%", height: "100%" }} />
        </div>
      </div>
      {label && <div style={{ position: "absolute", left: 120, top: 46 }}><Eyebrow color={C.accent}>{label}</Eyebrow></div>}
      {children}
    </AbsoluteFill>
  );
};

const Callout: React.FC<{ at: number; x: number; y: number; title: string; body?: string }> = ({ at, x, y, title, body }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)`, padding: "18px 24px", borderRadius: 14, background: "rgba(20,20,22,.94)", border: `1px solid ${C.accent}`, maxWidth: 560, boxShadow: "0 20px 60px rgba(0,0,0,.5)" }}>
      <div style={{ font: `600 30px ${display}`, color: C.ink }}>{title}</div>
      {body && <div style={{ font: `400 22px/1.4 ${ui}`, color: C.ink2, marginTop: 6 }}>{body}</div>}
    </div>
  );
};

// ── 3 · live product ────────────────────────────────────────────────────────────────────────
const Live = () => (
  <>
    <Audio src={staticFile("film/N2.wav")} />
    {F.live.map((c, i) => (
      <Sequence key={i} from={sec(c.at)} durationInFrames={sec(c.dur)}>
        <Screen src={staticFile(F.liveFile)} trim={sec(c.trim)} rate={c.rate} label={c.label} zoom={c.zoom as [number, number, number, number] | undefined} />
      </Sequence>
    ))}
    {F.liveCallouts.map((c, i) => <Callout key={i} {...c} at={sec(c.at)} />)}
  </>
);

// ── 4 · conversation: two speakers, matched preset voices ───────────────────────────────────
const Conversation = () => {
  const f = useCurrentFrame();
  const P = F.podcast;
  const narr = sec(N.N3 + .4);
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <Audio src={staticFile("film/N3.wav")} />
      {P.takes.map((t, i) => {
        const from = narr + P.takes.slice(0, i).reduce((n, x) => n + sec(x.end - x.start + .5), 0);
        return (
          <Sequence key={t.l} from={i === 0 ? 0 : from} durationInFrames={i === 0 ? from + sec(t.end - t.start + .5) : sec(t.end - t.start + .5)}>
            <PodcastTake t={t} narrated={i === 0 ? narr : 0} />
          </Sequence>
        );
      })}
      <div style={{ position: "absolute", left: 120, bottom: 40, font: `400 18px ${ui}`, color: C.ink3, opacity: fadeIn(f) }}>{P.attribution}</div>
    </AbsoluteFill>
  );
};

const PodcastTake: React.FC<{ t: Take; narrated: number }> = ({ t, narrated }) => {
  const f = useCurrentFrame();
  const src = staticFile(t.file);
  const trim = sec(t.start) - narrated;
  const now = (f - narrated) / FPS + t.start;
  const turn = F.podcast.turns.find(x => now >= x.start && now < x.end);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 120, top: 110, width: 1200, height: 675, borderRadius: 18, overflow: "hidden", border: `1px solid ${C.line}` }}>
        <Video src={src} trimBefore={Math.max(0, trim)} muted={f < narrated} volume={f < narrated ? 0 : 1} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        {f >= narrated && turn && (
          <div lang={t.lang} style={{ position: "absolute", left: 40, right: 40, bottom: 34, textAlign: "center" }}>
            <span style={{ display: "inline-block", padding: "10px 18px", borderRadius: 10, background: "rgba(0,0,0,.82)", font: `500 36px/1.4 ${ui}`, color: C.ink }}>{turn.text[t.lang]}<br /><span lang="en" style={{ font: `400 22px/1.4 ${ui}`, color: C.ink2 }}>{turn.text.en}</span></span>
          </div>
        )}
      </div>
      <div style={{ position: "absolute", left: 120, top: 46 }}><Eyebrow color={C.accent}>{f < narrated ? "Two speakers · one link" : `Dubbed into ${t.label}`}</Eyebrow></div>
      <div style={{ position: "absolute", left: 1360, top: 110, width: 440, display: "flex", flexDirection: "column", gap: 16 }}>
        {F.podcast.cast.map((c, i) => {
          const active = turn && turn.spk === c.spk && f >= narrated;
          const color = i === 0 ? C.spk0 : C.spk1;
          return (
            <div key={c.spk} style={{ padding: "22px 24px", borderRadius: 16, background: active ? "rgba(255,255,255,.06)" : C.s1, border: `1px solid ${active ? color : C.line}`, opacity: fadeIn(f, 6 + i * 8) }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, font: `600 30px ${display}`, color: C.ink }}><span style={{ width: 14, height: 14, borderRadius: 7, background: color }} />{c.name}</div>
              <div style={{ font: `500 20px ${mono}`, color, marginTop: 12 }}>voice → {c.voice}</div>
              <div style={{ font: `400 20px/1.4 ${ui}`, color: C.ink2, marginTop: 8 }}>{c.why}</div>
            </div>
          );
        })}
        <div style={{ padding: "18px 24px", borderRadius: 16, border: `1px dashed ${C.line}`, font: `400 20px/1.45 ${ui}`, color: C.ink3, opacity: fadeIn(f, 22) }}>Gemini listened to each speaker and chose the closest preset. No consent on file → no clone.</div>
      </div>
    </AbsoluteFill>
  );
};

// ── 5 · self-repair, from the real event log ─────────────────────────────────────────────────
const REPAIR = [
  { t: 0.0, kind: "", text: "[ja #13] synthesized 8.54 s for a 10.24 s slot" },
  { t: 3.8, kind: "bad", text: "[ja #13] Gemini heard a problem: Spoken in Korean instead of Japanese" },
  { t: 3.8, kind: "fix", text: "[ja #13] re-synthesizing" },
  { t: 7.6, kind: "bad", text: "[zh-Hans #15] Gemini heard a problem: Said ‘WhyBrick’ instead of ‘VibeRick’." },
  { t: 7.6, kind: "fix", text: "[zh-Hans #15] re-synthesizing" },
  { t: 12.3, kind: "good", text: "[ja #13] ✓ Gemini listened: correct" },
  { t: 19.3, kind: "good", text: "[zh-Hans #15] ✓ Gemini listened: correct" },
];
const Repair = () => {
  const f = useCurrentFrame();
  const colors: Record<string, string> = { bad: C.flag, fix: C.accent, good: C.pass, "": C.ink2 };
  const loop = ["measure", "shorten", "time-fit", "Gemini listens", "re-speak", "re-translate", "flag a human"];
  const lit = Math.min(loop.length - 1, Math.floor(f / sec(1.1)));
  const playAt = sec(N.N4 + .4);
  return (
    <AbsoluteFill style={{ background: C.ground, color: C.ink }}>
      <Audio src={staticFile("film/N4.wav")} />
      <Sequence from={playAt}><Audio src={staticFile("film/fixed.zh.wav")} /></Sequence>
      <Brand />
      <div style={{ position: "absolute", left: 160, top: 150 }}>
        <Eyebrow color={C.accent}>Check &amp; repair · every line</Eyebrow>
        <div style={{ display: "flex", gap: 12, marginTop: 28, flexWrap: "wrap", width: 1600 }}>
          {loop.map((s, i) => (
            <div key={s} style={{ padding: "12px 20px", borderRadius: 10, font: `500 28px ${mono}`, border: `1px solid ${i === loop.length - 1 ? C.flag : i <= lit ? C.accent : C.line}`, color: i === loop.length - 1 ? C.flag : i <= lit ? C.ink : C.ink3, background: i === lit ? "rgba(255,106,43,.14)" : "transparent" }}>{s}</div>
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", left: 160, top: 330, width: 1600, borderRadius: 18, background: C.s1, border: `1px solid ${C.line}`, padding: "26px 30px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", font: `600 26px ${ui}` }}><span>Agent activity</span><span style={{ font: `400 20px ${mono}`, color: C.ink3 }}>real events · public sample run</span></div>
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 10 }}>
          {REPAIR.map((r, i) => {
            const at = sec(1.4) + i * sec(1.5);
            return (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "110px 1fr", gap: 18, padding: "8px 16px", borderLeft: `3px solid ${r.kind === "bad" ? C.flag : r.kind === "fix" ? C.accent : "transparent"}`, opacity: fadeIn(f, at), transform: `translateY(${rise(f, at)}px)` }}>
                <span style={{ font: `400 22px ${mono}`, color: C.ink3 }}>+{r.t.toFixed(1)}s</span>
                <span style={{ font: `500 30px ${ui}`, color: colors[r.kind] }}>{r.text}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div lang="zh-Hans" style={{ position: "absolute", left: 160, bottom: 70, font: `500 36px ${ui}`, color: C.ink, opacity: fadeIn(f, playAt) }}>
        <span style={{ font: `500 22px ${mono}`, color: C.pass, marginRight: 18 }}>▶ FIXED TAKE</span>所以今天我就用自己的公司 <span style={{ color: C.pass }}>VibeRick</span> 来做个示范。
      </div>
    </AbsoluteFill>
  );
};

// ── 6 · edit one line ───────────────────────────────────────────────────────────────────────
const Edit = () => (
  <>
    <Audio src={staticFile("film/N5.wav")} />
    {F.edit.map((c, i) => (
      <Sequence key={i} from={sec(c.at)} durationInFrames={sec(c.dur)}>
        <Screen src={staticFile(F.editFile)} trim={sec(c.trim)} rate={c.rate} label="Edit · preview · accept" zoom={c.zoom as [number, number, number, number] | undefined} />
      </Sequence>
    ))}
  </>
);

// ── 7 · architecture ────────────────────────────────────────────────────────────────────────
const NODES = [
  { id: "fb", x: 120, y: 330, t: "Firebase Hosting", s: "Studio", at: 1.2 },
  { id: "api", x: 560, y: 330, t: "Cloud Run", s: "API · quotas · edits", at: 3.4 },
  { id: "job", x: 1000, y: 330, t: "Cloud Run Jobs", s: "One worker per dub", at: 4.6 },
  { id: "chirp", x: 1440, y: 170, t: "Chirp 3", s: "Words · times · speakers", at: 6.4, ai: true },
  { id: "gem", x: 1440, y: 330, t: "Gemini 3.8 Flash", s: "Proofread · translate · listen", at: 6.9, ai: true },
  { id: "tts", x: 1440, y: 490, t: "Gemini TTS", s: "Own voice · presets", at: 7.4, ai: true },
  { id: "fs", x: 560, y: 560, t: "Firestore", s: "Live agent events", at: 9.6 },
  { id: "gcs", x: 1000, y: 560, t: "Cloud Storage", s: "MP4 · M4A · SRT · VTT", at: 12.0 },
];
const EDGES: [string, string, number][] = [["fb", "api", 3.0], ["api", "job", 4.4], ["job", "chirp", 6.2], ["job", "gem", 6.7], ["job", "tts", 7.2], ["job", "fs", 9.4], ["fs", "fb", 10.6], ["job", "gcs", 11.8]];
const NW = 360, NH = 112;
const Arch = () => {
  const f = useCurrentFrame();
  const at = (s: number) => sec(s);
  const pos = Object.fromEntries(NODES.map(n => [n.id, n]));
  const numbersAt = sec(14.2);
  return (
    <AbsoluteFill style={{ background: C.ground, color: C.ink }}>
      <Audio src={staticFile("film/N6.wav")} />
      <Brand />
      <div style={{ position: "absolute", left: 120, top: 150 }}><Eyebrow color={C.accent}>All Google Cloud</Eyebrow></div>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {EDGES.map(([a, b, s], i) => {
          const A = pos[a], B = pos[b];
          const x1 = A.x + NW / 2, y1 = A.y + NH / 2, x2 = B.x + NW / 2, y2 = B.y + NH / 2;
          const p = interpolate(f, [at(s), at(s) + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return <line key={i} x1={x1} y1={y1} x2={x1 + (x2 - x1) * p} y2={y1 + (y2 - y1) * p} stroke={a === "fs" ? C.accent : "rgba(255,255,255,.28)"} strokeWidth={3} strokeDasharray={a === "fs" ? "8 8" : undefined} />;
        })}
      </svg>
      {NODES.map(n => (
        <div key={n.id} style={{ position: "absolute", left: n.x, top: n.y, width: NW, height: NH, padding: "20px 24px", borderRadius: 16, background: n.ai ? "#2a1710" : C.s1, border: `1px solid ${n.ai ? "rgba(255,106,43,.6)" : "rgba(255,255,255,.18)"}`, opacity: fadeIn(f, at(n.at)), transform: `translateY(${rise(f, at(n.at))}px)` }}>
          <div style={{ font: `600 30px ${display}`, letterSpacing: "-.015em" }}>{n.t}</div>
          <div style={{ font: `400 20px ${ui}`, color: C.ink3, marginTop: 4 }}>{n.s}</div>
        </div>
      ))}
      <div style={{ position: "absolute", left: 120, right: 120, top: 780, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", borderTop: `1px solid rgba(255,255,255,.18)`, opacity: fadeIn(f, numbersAt) }}>
        {[["366/369", "lines passed the listening check · full 15-min video"], ["125", "languages · Gemini 3.8 TTS, own or matched voice"], ["≈$0.03", "per dubbed minute"]].map(([b, s], i) => (
          <div key={b} style={{ paddingTop: 26, opacity: fadeIn(f, numbersAt + i * 12) }}>
            <div style={{ font: `600 96px/1 ${display}`, letterSpacing: "-.04em" }}>{b}</div>
            <div style={{ font: `400 24px ${ui}`, color: C.ink2, marginTop: 12 }}>{s}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ── 8 · consent + close ─────────────────────────────────────────────────────────────────────
const Close = () => {
  const f = useCurrentFrame();
  const end = 0;
  return (
    <AbsoluteFill style={{ background: C.ground, color: C.ink }}>
      <Audio src={staticFile("film/N7.wav")} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", opacity: fadeIn(f, end) }}>
        <Img src={staticFile("film/logo.png")} style={{ width: 88, height: 88, borderRadius: 18 }} />
        <div style={{ font: `600 120px/.98 ${display}`, letterSpacing: "-.045em", marginTop: 40 }}>Any video. 125 languages.<br /><span style={{ color: C.accent }}>Your own voice.</span></div>
        <div style={{ font: `500 40px ${ui}`, color: C.ink2, marginTop: 36 }}>You make the video. We take it to the world.</div>
        <div style={{ font: `500 36px ${mono}`, color: C.ink2, marginTop: 56 }}>viberick-dub.web.app</div>
        <div style={{ font: `400 24px ${ui}`, color: C.ink3, marginTop: 18 }}>Team VibeRick · Google Cloud AI Builder Cup 2026</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── timeline ────────────────────────────────────────────────────────────────────────────────
export const SCENES: { id: string; frames: number; C: React.FC }[] = [
  { id: "open", frames: coldOpenFrames, C: ColdOpen },
  { id: "title", frames: sec(N.N1 + .4 + N.N1b + 1.4), C: Title },
  { id: "live", frames: sec(Math.max(N.N2 + .8, F.liveTotal)), C: Live },
  { id: "conversation", frames: sec(N.N3 + .4) + F.podcast.takes.reduce((n, t) => n + sec(t.end - t.start + .5), 0), C: Conversation },
  { id: "repair", frames: sec(N.N4 + .4) + sec(F.repair.end - F.repair.start + .8), C: Repair },
  { id: "edit", frames: sec(Math.max(N.N5 + .8, F.editTotal)), C: Edit },
  { id: "arch", frames: sec(N.N6 + 1.4), C: Arch },
  { id: "close", frames: sec(N.N7 + 3.2), C: Close },
];
export const filmFrames = SCENES.reduce((n, s) => n + s.frames, 0);

export const Film: React.FC<{ only?: string }> = ({ only }) => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: C.ground, fontFamily: ui }}>
      <FontFaces />
      {SCENES.filter(s => !only || s.id === only).map(s => { const from = only ? 0 : at; at += s.frames; return <Sequence key={s.id} from={from} durationInFrames={s.frames} name={s.id}><s.C /></Sequence>; })}
    </AbsoluteFill>
  );
};
