import n from "./narration.json";
import type { ReactNode } from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
export const C = {
  bg: "#101a2b",
  ink: "#f2f5fb",
  muted: "#aebed5",
  blue: "#87b5ff",
  line: "#32435d",
};
export const Frame = ({
  children,
  kicker,
}: {
  children: ReactNode;
  kicker: string;
}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        background: C.bg,
        color: C.ink,
        fontFamily: "Arial, sans-serif",
        padding: "70px 90px",
      }}
    >
      <div
        style={{
          fontSize: 28,
          letterSpacing: 4,
          color: C.blue,
          marginBottom: 28,
        }}
      >
        VIBERICK DUB / {kicker}
      </div>
      <div
        style={{
          opacity: interpolate(f, [0, 12], [0, 1], {
            extrapolateRight: "clamp",
          }),
          flex: 1,
        }}
      >
        {children}
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 28,
          fontSize: 22,
          color: C.muted,
        }}
      >
        {n.enabled
          ? "LOCAL REVIEW PREVIEW · Listening review pending · AI narration: consenting creator voice"
          : "LOCAL REVIEW PREVIEW · Recorded evidence · No narration yet"}
      </div>
    </AbsoluteFill>
  );
};
export const title = {
  fontSize: 82,
  lineHeight: 1.08,
  letterSpacing: -3,
  margin: "10px 0 30px",
  fontWeight: 700,
} as const;
export const body = { fontSize: 40, lineHeight: 1.4, color: C.muted } as const;
