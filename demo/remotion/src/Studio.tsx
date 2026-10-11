import { Audio } from "@remotion/media";
import n from "./narration.json";
import { CanvasImage, staticFile, useVideoConfig } from "remotion";
import e from "./evidence.json";
import { Frame, title, C } from "./theme";
export const Studio = () => {
  const { fps } = useVideoConfig();
  return (
    <Frame kicker="ACTUAL LOCAL INTERFACE">
      {n.enabled && <Audio src={staticFile(n.studio.file)} premountFor={fps} />}
      <h1 style={{ ...title, fontSize: 74 }}>Review a translated line</h1>
      <div style={{ display: "flex", gap: 130, justifyContent: "center" }}>
        <CanvasImage
          src={staticFile(e.studio)}
          premountFor={fps}
          style={{
            width: 360,
            height: 680,
            objectFit: "contain",
            objectPosition: "top",
          }}
        />
        <div
          style={{
            fontSize: 40,
            lineHeight: 1.4,
            maxWidth: 850,
            paddingTop: 25,
          }}
        >
          <p>Language timelines follow rendered audio.</p>
          <p style={{ color: C.muted }}>
            Preview one edited line.
            <br />
            Accept it or keep the original.
          </p>
          <p style={{ fontSize: 28, color: C.blue }}>
            Mobile layout · refined audio selected.
            <br />
            This is not a recording of an accepted edit.
          </p>
        </div>
      </div>
    </Frame>
  );
};
