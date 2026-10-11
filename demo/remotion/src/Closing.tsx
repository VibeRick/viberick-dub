import { staticFile, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import n from "./narration.json";
import { Frame, title, body, C } from "./theme";
export const Closing = () => {
  const { fps } = useVideoConfig();
  return (
    <Frame kicker="WHAT RUNS BEHIND THE STUDIO">
      {n.enabled && (
        <Audio src={staticFile(n.closing.file)} premountFor={fps} />
      )}
      <h1 style={{ ...title, fontSize: 90 }}>A reviewable dubbing workflow</h1>
      <p style={{ ...body, color: C.ink, fontSize: 48 }}>
        Chirp timestamps → Gemini translation and voice
        <br />→ listening checks → creator review
      </p>
      <p style={{ ...body, marginTop: 55 }}>
        Cloud Run executes each job.
        <br />
        Firestore streams progress. Storage keeps the exports.
      </p>
      <p style={{ ...body, color: C.blue, marginTop: 55 }}>
        Next release gate: fresh audio review and deployed edit recovery.
      </p>
    </Frame>
  );
};
