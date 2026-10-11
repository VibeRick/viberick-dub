import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import p from "./podcast.json";
type Row = {
  id: number;
  start: number;
  end: number;
  spk: string;
  text: string;
  sourceText: string;
};
type Track = {
  lang: string;
  name: string;
  audio: string;
  start: number;
  end: number;
  rows: Row[];
};
const colors: Record<string, string> = { lex: "#f3b96c", demis: "#8ab9ff" };
export const PodcastTake = ({
  index = 0,
  extended = false,
}: {
  index?: number;
  extended?: boolean;
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const t = (extended ? p.extended : p.tracks[index]) as Track;
  const sec = t.start + frame / fps;
  const playing = t.rows.find((r) => sec >= r.start && sec < r.end);
  const row =
    playing ?? [...t.rows].reverse().find((r) => sec >= r.start) ?? t.rows[0];
  const span = extended ? t.end - t.start : 11.8;
  return (
    <AbsoluteFill
      style={{
        background: "#080f1b",
        color: "#f5f7fb",
        fontFamily: "Arial,sans-serif",
        padding: 70,
      }}
    >
      <div style={{ fontSize: 46, fontWeight: 800, letterSpacing: -1 }}>
        AI AUDIO DUBBING
      </div>
      <div
        style={{
          position: "absolute",
          right: 80,
          top: 62,
          fontSize: 48,
          fontWeight: 700,
          color: t.lang === "en" ? "white" : "#8ab9ff",
        }}
      >
        {t.name} <span style={{ fontSize: 24, color: "#aab8cb" }}>AUDIO</span>
      </div>
      <OffthreadVideo
        src={staticFile(p.source)}
        trimBefore={Math.round(t.start * fps)}
        muted
        style={{
          position: "absolute",
          left: 70,
          top: 165,
          objectFit: "contain",
          width: 1080,
          height: extended ? 470 : 608,
        }}
      />
      {extended ? (
        <div style={{ position: "absolute", left: 1220, top: 190, width: 615 }}>
          <div style={{ fontSize: 29, color: "#aab8cb", marginBottom: 28 }}>
            Same interview · complete answer
          </div>
          <div style={{ fontSize: 48, color: colors.demis }}>
            Demis Hassabis
          </div>
          <div style={{ fontSize: 26, color: "#aab8cb", marginTop: 12 }}>
            Algieba · AI preset voice
          </div>
          <div
            style={{
              fontSize: 32,
              lineHeight: 1.45,
              color: "#d0d9e5",
              marginTop: 38,
            }}
          >
            English gloss: A new physics idea would be checked with experts,
            validated and explained.
          </div>
          <div style={{ fontSize: 30, color: "#aab8cb", marginTop: 34 }}>
            Clip clock{" "}
            <span
              style={{ color: "white", fontVariantNumeric: "tabular-nums" }}
            >
              {sec.toFixed(2)}s
            </span>
          </div>
          <div
            style={{
              height: 30,
              background: colors.demis,
              position: "relative",
              marginTop: 22,
              opacity: 0.85,
            }}
          >
            <div
              style={{
                position: "absolute",
                left: `${Math.min(1, (sec - t.start) / span) * 100}%`,
                height: 42,
                top: -6,
                width: 4,
                background: "white",
              }}
            />
          </div>
        </div>
      ) : (
        <>
          {" "}
          <div
            style={{ position: "absolute", left: 1220, top: 173, width: 615 }}
          >
            <div style={{ fontSize: 29, color: "#aab8cb", marginBottom: 38 }}>
              {extended
                ? "Same interview · full answer"
                : "Same exchange · different language"}
            </div>
            <div style={{ marginBottom: 40 }}>
              <div
                style={{
                  fontSize: 46,
                  color: colors.lex,
                  opacity: playing?.spk === "lex" ? 1 : 0.5,
                }}
              >
                Lex Fridman
              </div>
              <div style={{ fontSize: 24, color: "#aab8cb", marginTop: 8 }}>
                {t.lang === "en"
                  ? "Original speaker"
                  : "Charon · AI preset voice"}
              </div>
            </div>
            <div style={{ marginBottom: 54 }}>
              <div
                style={{
                  fontSize: 46,
                  color: colors.demis,
                  opacity: playing?.spk === "demis" ? 1 : 0.5,
                }}
              >
                Demis Hassabis
              </div>
              <div style={{ fontSize: 24, color: "#aab8cb", marginTop: 8 }}>
                {t.lang === "en"
                  ? "Original speaker"
                  : "Algieba · AI preset voice"}
              </div>
            </div>
            <div style={{ fontSize: 28, color: "#aab8cb", marginBottom: 22 }}>
              Clip clock{" "}
              <span
                style={{ fontVariantNumeric: "tabular-nums", color: "white" }}
              >
                {sec.toFixed(2)}s
              </span>
            </div>
            {["lex", "demis"].map((spk) => (
              <div
                key={spk}
                style={{
                  position: "relative",
                  height: 34,
                  background: "#253248",
                  marginBottom: 15,
                  borderRadius: 4,
                }}
              >
                {t.rows
                  .filter((r) => r.spk === spk)
                  .map((r) => (
                    <div
                      key={r.id}
                      style={{
                        position: "absolute",
                        left: `${((r.start - t.start) / span) * 100}%`,
                        width: `${((r.end - r.start) / span) * 100}%`,
                        height: 34,
                        background: colors[spk],
                        opacity: playing?.id === r.id ? 1 : 0.45,
                        borderRadius: 4,
                      }}
                    />
                  ))}
                <div
                  style={{
                    position: "absolute",
                    left: `${Math.min(1, (sec - t.start) / span) * 100}%`,
                    height: 44,
                    top: -5,
                    width: 3,
                    background: "white",
                  }}
                />
              </div>
            ))}
            <div style={{ fontSize: 23, color: "#aab8cb", marginTop: 22 }}>
              Actual speech intervals · speaker colors preserved
            </div>
          </div>
        </>
      )}
      <div
        style={{
          position: "absolute",
          top: extended ? 680 : 798,
          left: 86,
          right: 86,
        }}
      >
        <div
          style={{
            fontSize: extended ? 44 : 40,
            lineHeight: 1.34,
            color: colors[row.spk],
          }}
        >
          {row.text}
        </div>
        {t.lang !== "en" && !extended && (
          <div
            style={{
              fontSize: 27,
              lineHeight: 1.4,
              color: "#b5c1d2",
              marginTop: 13,
            }}
          >
            English {extended ? "gloss" : "source"}:{" "}
            {extended
              ? "A new physics idea would be checked with experts, validated and explained."
              : row.sourceText}
          </div>
        )}
      </div>
      <div
        style={{
          position: "absolute",
          left: 85,
          bottom: 22,
          fontSize: 20,
          color: "#8294ac",
        }}
      >
        {p.sourceCredit} · Recorded output ·{" "}
        {t.lang === "en" ? "Source audio" : "Distinct preset voices"}
      </div>
      <Audio src={staticFile(t.audio)} premountFor={fps} />
    </AbsoluteFill>
  );
};
