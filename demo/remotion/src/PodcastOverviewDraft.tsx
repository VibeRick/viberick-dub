import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import p from "./podcast.json";
import takes from "./short.json";
import { PodcastTake } from "./PodcastTake";
export const PodcastSource = () => <PodcastTake index={0} />;
const ink = "#f4f7ff",
  muted = "#9eacc2",
  lex = "#ffca87",
  demis = "#97beff";
const starts = [3, 8, 13];
const ease = Easing.bezier(0.22, 1, 0.36, 1);
export const PodcastOverviewDraft = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sec = f / fps;
  const flow = interpolate(f, [1 * fps, 3 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const ending = interpolate(f, [18 * fps, 19 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
  const phase =
    sec < 1.5
      ? "One conversation. Three languages."
      : sec < 3
        ? "Gemini translates, speaks and listens back."
        : sec < 18
          ? "Switch languages. Keep both speakers."
          : "Listen. Compare. Publish.";
  return (
    <AbsoluteFill
      style={{
        background: "#080f20",
        color: ink,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 84,
          top: 48,
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 2,
        }}
      >
        VIBERICK DUB
      </div>
      <div
        style={{
          position: "absolute",
          right: 84,
          top: 48,
          fontSize: 32,
          color: muted,
        }}
      >
        Built with Gemini · Google Cloud
      </div>
      <h1
        style={{
          position: "absolute",
          left: 80,
          top: 109,
          margin: 0,
          fontSize: 100,
          lineHeight: 1.05,
          letterSpacing: -4,
        }}
      >
        AI AUDIO <span style={{ color: demis }}>DUBBING</span>
      </h1>
      <div
        style={{
          position: "absolute",
          left: 84,
          top: 240,
          fontSize: 44,
          color: muted,
        }}
      >
        {phase}
      </div>
      <svg
        width="1920"
        height="1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <path
          d="M 654 598 H 774"
          fill="none"
          stroke="#36425b"
          strokeWidth="3"
        />
        <path
          d="M 1112 598 H 1160 V 400 H 1230 M 1160 598 H 1230 M 1160 598 V 794 H 1230"
          fill="none"
          stroke="#36425b"
          strokeWidth="3"
        />
        <path
          d="M 654 598 H 774"
          fill="none"
          stroke="#94baff"
          strokeWidth="4"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - flow}
        />
        <path
          d="M 1112 598 H 1160 V 400 H 1230 M 1160 598 H 1230 M 1160 598 V 794 H 1230"
          fill="none"
          stroke="#94baff"
          strokeWidth="4"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - flow}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: 80,
          top: 332,
          width: 574,
          height: 530,
          border: "1px solid #33415b",
          borderRadius: 26,
          background: "#101a2d",
          padding: 26,
          boxSizing: "border-box",
        }}
      >
        <div style={{ fontSize: 32, color: muted, marginBottom: 20 }}>
          ORIGINAL · ENGLISH
        </div>
        <div style={{ display: "flex", gap: 18 }}>
          <div style={{ width: 250 }}>
            <Img
              src={staticFile(p.lexImage)}
              style={{
                width: 250,
                height: 154,
                objectFit: "cover",
                borderRadius: 12,
              }}
            />
            <div style={{ fontSize: 32, color: lex, marginTop: 12 }}>
              Lex Fridman
            </div>
          </div>
          <div style={{ width: 250 }}>
            <Img
              src={staticFile(p.demisImage)}
              style={{
                width: 250,
                height: 154,
                objectFit: "cover",
                borderRadius: 12,
              }}
            />
            <div style={{ fontSize: 32, color: demis, marginTop: 12 }}>
              Demis Hassabis
            </div>
          </div>
        </div>
        <div
          style={{ fontSize: 39, lineHeight: 1.25, color: lex, marginTop: 28 }}
        >
          “And you would be in the room for that.”
        </div>
        <div style={{ fontSize: 42, color: demis, marginTop: 17 }}>
          “Absolutely.”
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 774,
          top: 468,
          width: 338,
          height: 260,
          borderRadius: 32,
          background: "linear-gradient(135deg,#172a4d,#241a40)",
          border: "1px solid #6384b0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          boxShadow: `0 0 ${30 + flow * 40}px #3c70be25`,
        }}
      >
        <div
          style={{
            fontSize: 77,
            fontWeight: 600,
            letterSpacing: -3,
            background: "linear-gradient(100deg,#85c1ff,#c8a7ff)",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          Gemini
        </div>
        <div
          style={{
            fontSize: 28,
            color: "#bdc8df",
            marginTop: 18,
            textAlign: "center",
            lineHeight: 1.5,
          }}
        >
          Translate → Speak
          <br />
          Listen back &amp; check
        </div>
      </div>
      {takes.map((take, i) => {
        const start = starts[i];
        const active = interpolate(
          sec,
          [start, start + 0.8, start + 4.1, start + 5],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease },
        );
        const a = start + 0.8,
          b = a + take.clips[0].duration + 0.25;
        const who =
          sec >= a && sec < a + take.clips[0].duration
            ? "lex"
            : sec >= b && sec < b + take.clips[1].duration
              ? "demis"
              : null;
        return (
          <div
            key={take.lang}
            style={{
              position: "absolute",
              left: 1230,
              top: 320 + i * 198,
              width: 606,
              height: 180,
              borderRadius: 20,
              background: active > 0.01 ? "#172842" : "#111c30",
              border: `2px solid rgba(151,190,255,${0.18 + active * 0.75})`,
              boxShadow: `0 0 ${active * 35}px #559eff25`,
              padding: "19px 28px",
              boxSizing: "border-box",
              translate: `${-active * 8}px 0`,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 14,
              }}
            >
              <b style={{ fontSize: 36 }}>{take.name}</b>
              <span style={{ fontSize: 24, color: demis, opacity: active }}>
                ● LISTEN
              </span>
            </div>
            <div
              style={{
                fontSize: 34,
                lineHeight: 1.25,
                color: lex,
                opacity: who === "demis" ? 0.55 : 1,
              }}
            >
              Lex <span style={{ color: ink }}>· {take.clips[0].text}</span>
            </div>
            <div
              style={{
                fontSize: 34,
                lineHeight: 1.25,
                color: demis,
                marginTop: 8,
                opacity: who === "lex" ? 0.55 : 1,
              }}
            >
              Demis <span style={{ color: ink }}>· {take.clips[1].text}</span>
            </div>
          </div>
        );
      })}
      <Sequence
        from={Math.round((starts[0] + 0.8) * fps)}
        durationInFrames={Math.ceil(takes[0].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[0].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[0] + 0.8 + takes[0].clips[0].duration + 0.25) * fps,
        )}
        durationInFrames={Math.ceil(takes[0].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[0].clips[1].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round((starts[1] + 0.8) * fps)}
        durationInFrames={Math.ceil(takes[1].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[1].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[1] + 0.8 + takes[1].clips[0].duration + 0.25) * fps,
        )}
        durationInFrames={Math.ceil(takes[1].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[1].clips[1].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round((starts[2] + 0.8) * fps)}
        durationInFrames={Math.ceil(takes[2].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[2].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[2] + 0.8 + takes[2].clips[0].duration + 0.25) * fps,
        )}
        durationInFrames={Math.ceil(takes[2].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(takes[2].clips[1].file)} premountFor={fps} />
      </Sequence>
      <div
        style={{
          position: "absolute",
          left: 84,
          bottom: 98,
          fontSize: 37,
          color: muted,
          opacity: 1 - ending,
        }}
      >
        Two speakers → three languages → one review screen.
      </div>
      <div
        style={{
          position: "absolute",
          left: 84,
          bottom: 92,
          fontSize: 48,
          fontWeight: 600,
          color: demis,
          opacity: ending,
        }}
      >
        viberick-dub.web.app
      </div>
      <div
        style={{
          position: "absolute",
          left: 84,
          bottom: 43,
          fontSize: 23,
          color: "#7f90ad",
        }}
      >
        Actual generated audio · Distinct AI preset voices · Lex Fridman Podcast
        #475 excerpt
      </div>
      <div
        style={{
          position: "absolute",
          right: 84,
          bottom: 48,
          fontSize: 24,
          color: "#7f90ad",
        }}
      >
        Workflow illustration
      </div>
    </AbsoluteFill>
  );
};
