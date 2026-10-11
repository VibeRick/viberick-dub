import { Audio, Video } from "@remotion/media";
import { Series, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import e from "./evidence.json";
import { C, Frame, title } from "./theme";
const Take = ({ index }: { index: number }) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const track = e.tracks[index];
  const sec = frame / fps;
  return (
    <Frame kicker="SAME PHRASE / ONE VOICE AT A TIME">
      <h1 style={{ ...title, fontSize: 76, marginBottom: 26 }}>{track.name}</h1>
      <div style={{ display: "flex", gap: 60 }}>
        <div style={{ width: 900 }}>
          <Video
            src={staticFile(e.video)}
            muted
            premountFor={fps}
            objectFit="contain"
            style={{ width: 900, height: 450, background: "#050910" }}
          />
          <p
            style={{
              fontSize: 38,
              lineHeight: 1.35,
              color: C.ink,
              margin: "18px 0 8px",
            }}
          >
            {track.text}
          </p>
          {track.lang !== "en" && (
            <p
              style={{
                fontSize: 26,
                lineHeight: 1.35,
                color: C.muted,
                margin: "8px 0",
              }}
            >
              English: {e.tracks[1].text}
            </p>
          )}
          <p
            style={{
              fontSize: 22,
              lineHeight: 1.3,
              color: C.muted,
              margin: "12px 0",
            }}
          >
            Recorded output · same source moment
          </p>
        </div>
        <div style={{ width: 780, paddingTop: 10 }}>
          <div
            style={{
              fontSize: 48,
              fontVariantNumeric: "tabular-nums",
              marginBottom: 38,
            }}
          >
            Source clock {(e.offset + sec).toFixed(2)}s
          </div>
          {e.tracks.map((t, i) => (
            <div
              key={t.lang}
              style={{ marginBottom: 34, opacity: i === index ? 1 : 0.48 }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 30,
                  marginBottom: 10,
                }}
              >
                <span>
                  {t.name}
                  {i === index ? " · audible" : ""}
                </span>
                <span>{(t.end - t.start).toFixed(2)}s</span>
              </div>
              <div
                style={{
                  height: 36,
                  position: "relative",
                  background: C.line,
                  borderRadius: 5,
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: `${(Math.max(0, t.start - e.offset) / 8) * 100}%`,
                    width: `${((t.end - Math.max(t.start, e.offset)) / 8) * 100}%`,
                    height: 36,
                    background: i === index ? C.blue : "#6c829f",
                    borderRadius: 5,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: `${(sec / 8) * 100}%`,
                    height: 48,
                    top: -6,
                    width: 3,
                    background: "white",
                  }}
                />
              </div>
            </div>
          ))}
          <p style={{ fontSize: 26, color: C.muted, lineHeight: 1.45 }}>
            Bars show actual rendered speech intervals.
            <br />
            The cursor shares the source video clock.
          </p>
        </div>
      </div>
      <Audio src={staticFile(track.audio)} premountFor={fps} />
    </Frame>
  );
};
export const Proof = () => {
  const { fps } = useVideoConfig();
  return (
    <Series>
      <Series.Sequence
        name="Original Korean"
        durationInFrames={Math.ceil((e.tracks[0].end - e.offset + 0.35) * fps)}
        premountFor={fps}
      >
        <Take index={0} />
      </Series.Sequence>
      <Series.Sequence
        name="English dub"
        durationInFrames={Math.ceil((e.tracks[1].end - e.offset + 0.35) * fps)}
        premountFor={fps}
      >
        <Take index={1} />
      </Series.Sequence>
      <Series.Sequence
        name="Japanese dub"
        durationInFrames={Math.ceil((e.tracks[2].end - e.offset + 0.35) * fps)}
        premountFor={fps}
      >
        <Take index={2} />
      </Series.Sequence>
      <Series.Sequence
        name="Chinese dub"
        durationInFrames={Math.ceil((e.tracks[3].end - e.offset + 0.35) * fps)}
        premountFor={fps}
      >
        <Take index={3} />
      </Series.Sequence>
    </Series>
  );
};
