import n from "./narration.json";
import e from "./evidence.json";
import { Series, useVideoConfig } from "remotion";
import { Opening } from "./Opening";
import { Proof } from "./Proof";
import { Studio } from "./Studio";
import { Evidence } from "./Evidence";
import { Closing } from "./Closing";
export const Demo = () => {
  const { fps } = useVideoConfig();
  return (
    <Series>
      <Series.Sequence
        name="Opening"
        durationInFrames={Math.ceil(n.opening.duration * fps)}
        premountFor={fps}
      >
        <Opening />
      </Series.Sequence>
      <Series.Sequence
        name="Four audible takes"
        durationInFrames={e.tracks.reduce(
          (sum, t) => sum + Math.ceil((t.end - e.offset + 0.35) * fps),
          0,
        )}
        premountFor={fps}
      >
        <Proof />
      </Series.Sequence>
      <Series.Sequence
        name="Actual studio"
        durationInFrames={Math.ceil(n.studio.duration * fps)}
        premountFor={fps}
      >
        <Studio />
      </Series.Sequence>
      <Series.Sequence
        name="Recorded repair"
        durationInFrames={Math.ceil(n.evidence.duration * fps)}
        premountFor={fps}
      >
        <Evidence />
      </Series.Sequence>
      <Series.Sequence
        name="Architecture and next gate"
        durationInFrames={Math.ceil(n.closing.duration * fps)}
        premountFor={fps}
      >
        <Closing />
      </Series.Sequence>
    </Series>
  );
};
