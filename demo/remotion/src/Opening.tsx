import { staticFile, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import n from "./narration.json";
import { Frame, title, body, C } from "./theme";
export const Opening = () => {
  const { fps } = useVideoConfig();
  return (
    <Frame kicker="THE PROOF">
      {n.enabled && (
        <Audio src={staticFile(n.opening.file)} premountFor={fps} />
      )}
      <h1 style={{ ...title, fontSize: 116, maxWidth: 1500 }}>
        One phrase.
        <br />
        Four ways to hear it.
      </h1>
      <p style={{ ...body, maxWidth: 1450 }}>
        “Even my parents ask ChatGPT now.”
      </p>
      <p style={{ ...body, color: C.blue, marginTop: 70 }}>
        One creator. The same voice.
        <br />
        English, Japanese and Chinese.
      </p>
      <p style={{ fontSize: 26, color: C.muted }}>
        Voice replication with the creator’s consent.
      </p>
    </Frame>
  );
};
