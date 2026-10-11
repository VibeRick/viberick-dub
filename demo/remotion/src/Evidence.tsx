import { Audio } from "@remotion/media";
import n from "./narration.json";
import { staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import e from "./evidence.json";
import { Frame, title, C } from "./theme";
export const Evidence = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const events = e.events as Array<{
    do?: string;
    ok?: boolean;
    issue?: string;
    id?: number;
    t: number;
  }>;
  const key = events
    .filter(
      (x) =>
        x.ok === false ||
        x.do === "retranslate" ||
        x.do === "resynth" ||
        x.ok === true,
    )
    .slice(-4);
  return (
    <Frame kicker="RECORDED AGENT EVIDENCE">
      {n.enabled && (
        <Audio src={staticFile(n.evidence.file)} premountFor={fps} />
      )}
      <h1 style={{ ...title, fontSize: 78 }}>
        A check can trigger another take
      </h1>
      <p style={{ fontSize: 30, color: C.muted }}>
        Historical Japanese line {events[0]?.id ?? "—"} · {e.eventRun} · event
        order replay
      </p>
      <div style={{ marginTop: 50 }}>
        {key.length ? (
          key.map((x, i) => (
            <div
              key={i}
              style={{
                opacity: frame >= i * 2 * fps ? 1 : 0.16,
                borderTop: `1px solid ${C.line}`,
                padding: "20px 0",
                display: "flex",
                gap: 40,
              }}
            >
              <div
                style={{
                  fontSize: 36,
                  color: x.ok === false ? "#ffc08b" : C.blue,
                  width: 340,
                }}
              >
                {x.ok === false
                  ? "Check failed"
                  : x.ok === true
                    ? "Recheck passed"
                    : x.do}
              </div>
              <div style={{ fontSize: 32, lineHeight: 1.4, maxWidth: 1240 }}>
                {x.issue ||
                  "Recorded automatic result; human listening still required."}
              </div>
            </div>
          ))
        ) : (
          <p style={{ fontSize: 44 }}>
            No suitable repair sequence selected for this run.
          </p>
        )}
      </div>
      <p style={{ fontSize: 30, color: C.muted, marginTop: 40 }}>
        Automatic checks help find problems. They do not certify the meaning or
        naturalness.
      </p>
    </Frame>
  );
};
