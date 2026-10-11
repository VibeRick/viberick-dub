import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Freeze,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import source from "./podcast.json";
import tracks from "./short.json";
const starts = [4, 10, 16],
  base = 11.45;
const gold = "#ffc987",
  blue = "#95bbff",
  muted = "#9dafca";
const stamp = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${(s % 60).toFixed(3).padStart(6, "0")}`;
const Footage = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Freeze frame={Math.min(f, Math.round(2.71 * fps))}>
      <OffthreadVideo
        src={staticFile(source.source)}
        trimBefore={Math.round(base * fps)}
        muted
        style={{ width: 862, height: 485, objectFit: "cover" }}
      />
    </Freeze>
  );
};
export const StudioDemo = () => {
  const frame = useCurrentFrame(),
    { fps } = useVideoConfig(),
    sec = frame / fps;
  const index = sec < 10 ? 0 : sec < 16 ? 1 : 2;
  const playhead =
    base + Math.max(0, Math.min(2.71, sec - starts[index] - 0.8));
  const current = tracks[index];
  const speaking = current.clips.filter(
    (c) =>
      playhead >= c.start &&
      playhead < c.end &&
      sec >= starts[index] + 0.8 &&
      sec < starts[index] + 3.6,
  );
  const closing = interpolate(sec, [22, 23], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        background: "#08111e",
        color: "#eff5ff",
        fontFamily: "Arial,sans-serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 70,
          top: 35,
          fontSize: 31,
          fontWeight: 700,
          letterSpacing: 1,
        }}
      >
        VIBERICK DUB <span style={{ color: blue }}> / GEMINI AUDIO STUDIO</span>
      </div>
      <div
        style={{
          position: "absolute",
          right: 70,
          top: 39,
          fontSize: 29,
          color: muted,
        }}
      >
        Creators · Podcasts · Course teams
      </div>
      <h1
        style={{
          position: "absolute",
          left: 66,
          top: 92,
          fontSize: 83,
          lineHeight: 1,
          letterSpacing: -3,
          margin: 0,
        }}
      >
        AI AUDIO DUBBING
      </h1>
      <div
        style={{
          position: "absolute",
          right: 70,
          top: 109,
          textAlign: "right",
        }}
      >
        <b style={{ fontSize: 42, color: blue }}>130+ languages</b>
        <div style={{ fontSize: 24, color: muted, marginTop: 9 }}>
          Gemini TTS capability · App verified in 4
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 70,
          top: 208,
          width: 862,
          height: 485,
          borderRadius: 18,
          overflow: "hidden",
          border: "1px solid #3c4e66",
          background: "#131e32",
        }}
      >
        <Freeze frame={0}>
          <OffthreadVideo
            src={staticFile(source.source)}
            trimBefore={Math.round(base * fps)}
            muted
            style={{ width: 862, height: 485, objectFit: "cover" }}
          />
        </Freeze>
        <Sequence
          from={Math.round((starts[0] + 0.8) * fps)}
          durationInFrames={Math.round(5.2 * fps)}
          premountFor={fps}
        >
          <Footage />
        </Sequence>
        <Sequence
          from={Math.round((starts[1] + 0.8) * fps)}
          durationInFrames={Math.round(5.2 * fps)}
          premountFor={fps}
        >
          <Footage />
        </Sequence>
        <Sequence
          from={Math.round((starts[2] + 0.8) * fps)}
          durationInFrames={Math.round(5.2 * fps)}
          premountFor={fps}
        >
          <Footage />
        </Sequence>
        <div
          style={{
            position: "absolute",
            left: 18,
            top: 18,
            padding: "10px 15px",
            fontSize: 28,
            background: "#061120dc",
            borderRadius: 8,
          }}
        >
          SOURCE ENGLISH ·{" "}
          <span style={{ fontVariantNumeric: "tabular-nums" }}>
            {stamp(source.sourceOffset + playhead)}
          </span>
        </div>
        <div
          style={{
            position: "absolute",
            left: 22,
            right: 22,
            bottom: 111,
            padding: "12px 16px",
            background: "#041020c9",
            borderRadius: 10,
            fontSize: 32,
            lineHeight: 1.25,
          }}
        >
          {playhead >= 13.4
            ? "“Absolutely.”"
            : "“And you would be in the room for that.”"}
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            padding: "55px 22px 20px",
            background: "linear-gradient(transparent,#040b16)",
            display: "flex",
            gap: 24,
          }}
        >
          {["lex", "demis"].map((who, i) => (
            <div
              key={who}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 13,
                opacity:
                  speaking.length && !speaking.some((c) => c.speaker === who)
                    ? 0.5
                    : 1,
              }}
            >
              <Img
                src={staticFile(i ? source.demisImage : source.lexImage)}
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 28,
                  objectFit: "cover",
                  border: `2px solid ${i ? blue : gold}`,
                }}
              />
              <div>
                <b style={{ fontSize: 30, color: i ? blue : gold }}>
                  {i ? "02 Demis Hassabis" : "01 Lex Fridman"}
                </b>
                <div style={{ fontSize: 21, color: "#c3ccdb" }}>
                  Distinct AI preset voice
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 75,
          top: 712,
          fontSize: 26,
          color: muted,
        }}
      >
        Creator voice cloning: consent + voice matching{" "}
        <span style={{ color: "#d7e2f7" }}>· This interview uses presets</span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 978,
          top: 207,
          fontSize: 28,
          color: muted,
        }}
      >
        SIMULTANEOUS SUBTITLES{" "}
        <span style={{ marginLeft: 32, color: blue }}>
          Gemini translation · TTS · QC
        </span>
      </div>
      {tracks.map((t, i) => {
        const a = starts[i],
          focus = interpolate(sec, [a, a + 0.8, a + 5.1, a + 6], [0, 1, 1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
        return (
          <div
            key={t.lang}
            style={{
              position: "absolute",
              left: 976,
              top: 254 + i * 156,
              width: 874,
              height: 150,
              boxSizing: "border-box",
              padding: "12px 22px",
              borderRadius: 14,
              border: `2px solid rgba(149,187,255,${0.15 + focus * 0.8})`,
              background: focus > 0.01 ? "#172842" : "#111d30",
              boxShadow: `0 0 ${focus * 25}px #468fe320`,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 7,
              }}
            >
              <b style={{ fontSize: 31 }}>{t.name}</b>
              <span style={{ fontSize: 23, color: blue, opacity: focus }}>
                ● AUDIBLE
              </span>
            </div>
            <div style={{ fontSize: 33, lineHeight: 1.15 }}>
              <span style={{ color: gold, fontWeight: 700 }}>01 Lex</span> ·{" "}
              {t.clips[0].text}
            </div>
            <div style={{ fontSize: 33, lineHeight: 1.15, marginTop: 7 }}>
              <span style={{ color: blue, fontWeight: 700 }}>02 Demis</span> ·{" "}
              {t.clips[1].text}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 70,
          top: 748,
          fontSize: 29,
          color: "#d8e5fc",
        }}
      >
        SOURCE & DUB TIMING
      </div>
      <div
        style={{
          position: "absolute",
          left: 286,
          top: 786,
          right: 75,
          fontSize: 23,
          color: muted,
        }}
      >
        {[11, 12, 13, 14.6].map((t) => (
          <span
            key={t}
            style={{
              position: "absolute",
              left: `${((t - 11) / 3.6) * 100}%`,
              translate: "-50% 0",
            }}
          >
            {stamp(source.sourceOffset + t)}
          </span>
        ))}
      </div>
      {[
        {
          name: "Original",
          clips: tracks[0].clips.map((c) => ({
            ...c,
            start: c.source_start,
            end: c.source_end,
          })),
        },
        ...tracks,
      ].map((t, i) => (
        <div
          key={t.name}
          style={{
            position: "absolute",
            left: 74,
            top: 821 + i * 37,
            right: 75,
            height: 28,
            display: "flex",
            alignItems: "center",
            gap: 22,
          }}
        >
          <div
            style={{
              width: 190,
              fontSize: 26,
              color: i === index + 1 ? blue : muted,
            }}
          >
            {t.name}
          </div>
          <div
            style={{
              flex: 1,
              height: 24,
              background: "#19263c",
              position: "relative",
              borderRadius: 5,
            }}
          >
            {t.clips.map((c) => (
              <div
                key={c.speaker}
                style={{
                  position: "absolute",
                  left: `${((c.start - 11) / 3.6) * 100}%`,
                  width: `${((c.end - c.start) / 3.6) * 100}%`,
                  height: 24,
                  background: c.speaker === "lex" ? gold : blue,
                  opacity: i === 0 || i === index + 1 ? 1 : 0.55,
                  borderRadius: 4,
                }}
              />
            ))}
            <div
              style={{
                position: "absolute",
                left: `${((playhead - 11) / 3.6) * 100}%`,
                top: -5,
                height: 34,
                width: 3,
                background: "#fff",
              }}
            />
          </div>
        </div>
      ))}

      <Sequence
        from={Math.round((starts[0] + 0.8) * fps)}
        durationInFrames={Math.ceil(tracks[0].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[0].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[0] + 0.8 + tracks[0].clips[1].start - base) * fps,
        )}
        durationInFrames={Math.ceil(tracks[0].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[0].clips[1].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round((starts[1] + 0.8) * fps)}
        durationInFrames={Math.ceil(tracks[1].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[1].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[1] + 0.8 + tracks[1].clips[1].start - base) * fps,
        )}
        durationInFrames={Math.ceil(tracks[1].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[1].clips[1].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round((starts[2] + 0.8) * fps)}
        durationInFrames={Math.ceil(tracks[2].clips[0].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[2].clips[0].file)} premountFor={fps} />
      </Sequence>
      <Sequence
        from={Math.round(
          (starts[2] + 0.8 + tracks[2].clips[1].start - base) * fps,
        )}
        durationInFrames={Math.ceil(tracks[2].clips[1].duration * fps)}
        premountFor={fps}
      >
        <Audio src={staticFile(tracks[2].clips[1].file)} premountFor={fps} />
      </Sequence>
      <div
        style={{
          position: "absolute",
          left: 70,
          top: 973,
          right: 70,
          borderTop: "1px solid #33435b",
          paddingTop: 18,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ opacity: 1 - closing, fontSize: 27, color: muted }}>
          Per-language work: Translate → Voice recording → Subtitle timing →
          Review
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 18,
            fontSize: 29,
            color: blue,
            opacity: closing,
          }}
        >
          One studio for multilingual audio, subtitles and human review.
        </div>
        <div style={{ fontSize: 29, fontWeight: 700, color: "#dce8ff" }}>
          viberick-dub.web.app
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 70,
          bottom: 14,
          fontSize: 18,
          color: "#7e8faa",
        }}
      >
        Recorded outputs · Transcript-assisted source alignment · Gemini model
        language coverage: Google documentation
      </div>
    </AbsoluteFill>
  );
};
