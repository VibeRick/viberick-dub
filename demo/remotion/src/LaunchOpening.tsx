import { Audio } from "@remotion/media";
import { AbsoluteFill, OffthreadVideo, Series, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import evidence from "./evidence.json";

const palette = { paper: "#eef2f7", ink: "#17263a", muted: "#425570", blue: "#265fb0" };

export const VoiceReveal = ({ index = 0 }: { index?: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const track = evidence.tracks[index];
  const labels = ["The original recording", "Now in English", "Now in Japanese"];
  return <AbsoluteFill style={{ background: palette.paper, color: palette.ink, fontFamily: "Arial, Noto Sans KR, Noto Sans JP, sans-serif", padding: "64px 88px" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 30 }}>
      <b>VibeRick Dub</b><span style={{ color: palette.muted }}>One recording. More audiences.</span>
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 64, marginTop: 65 }}>
      <div style={{ width: 470, flexShrink: 0 }}>
        <div style={{ fontSize: 30, marginBottom: 28, color: palette.blue }}>{index === 0 ? "Source video" : "Actual generated audio"}</div>
        <h1 style={{ fontSize: 84, lineHeight: 1.06, letterSpacing: "-3px", margin: 0 }}>{labels[index]}</h1>
        <div style={{ marginTop: 42, display: "flex", gap: 12 }}>
          {['한국어', 'English', '日本語'].map((name, i) => <span key={name} style={{ fontSize: 25, padding: "12px 17px", borderRadius: 8, background: i === index ? palette.ink : "#dce4ef", color: i === index ? "white" : palette.muted }}>{name}</span>)}
        </div>
        <p style={{ fontSize: 28, lineHeight: 1.5, marginTop: 40, color: palette.muted }}>{index === 0 ? "Recorded by Jaeho, the creator." : "His consented voice. A different language."}</p>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ aspectRatio: "16/9", background: "black", borderRadius: 16, overflow: "hidden", boxShadow: "0 18px 55px #17263a20" }}>
          <OffthreadVideo src={staticFile(evidence.video)} muted style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
        <p style={{ fontSize: 42, lineHeight: 1.4, margin: "28px 0 0", minHeight: 125 }}>{track.text}</p>
      </div>
    </div>
    <div style={{ position: "absolute", left: 88, right: 88, bottom: 55, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 24, color: palette.muted }}>
      <span>Same source moment · Real outputs · No lip animation</span><span>{index + 1} / 3</span>
    </div>
    <div style={{ position: "absolute", bottom: 0, left: 0, height: 6, background: palette.blue, width: `${interpolate(frame, [0, 4.65 * fps], [0, 100], { extrapolateRight: "clamp" })}%` }} />
    <Audio src={staticFile(track.audio)} premountFor={fps} />
  </AbsoluteFill>;
};

export const LaunchPromise = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return <AbsoluteFill style={{ background: palette.ink, color: "white", fontFamily: "Arial, sans-serif", justifyContent: "center", padding: "80px 120px" }}>
    <div style={{ fontSize: 32, color: "#b8cce7", marginBottom: 42 }}>VibeRick Dub</div>
    <h1 style={{ fontSize: 106, lineHeight: 1.1, letterSpacing: "-4px", margin: 0, opacity: interpolate(frame, [0, .3 * fps], [0, 1], { extrapolateRight: "clamp" }) }}>You made the video.<br />We’ll handle the languages.</h1>
    <p style={{ fontSize: 42, color: "#cad6e7", marginTop: 50 }}>Multilingual audio. Synced subtitles. One workflow.</p>
    <div style={{ position: "absolute", bottom: 65, fontSize: 30 }}>viberick-dub.web.app</div>
  </AbsoluteFill>;
};

export const LaunchOpening = () => {
  const { fps } = useVideoConfig();
  return <Series>
    <Series.Sequence name="Original complete sentence" durationInFrames={140} premountFor={fps}><VoiceReveal index={0} /></Series.Sequence>
    <Series.Sequence name="English complete sentence" durationInFrames={138} premountFor={fps}><VoiceReveal index={1} /></Series.Sequence>
    <Series.Sequence name="Japanese complete sentence" durationInFrames={134} premountFor={fps}><VoiceReveal index={2} /></Series.Sequence>
    <Series.Sequence name="The product promise" durationInFrames={120} premountFor={fps}><LaunchPromise /></Series.Sequence>
  </Series>;
};
