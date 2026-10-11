import { Series, useVideoConfig } from "remotion";
import p from "./podcast.json";
import { PodcastOpening } from "./PodcastOpening";
import { PodcastTake } from "./PodcastTake";
import { PodcastStudio } from "./PodcastStudio";
export const PodcastSource = () => <PodcastTake index={0} />;
export const PodcastLong = () => {
  const { fps } = useVideoConfig();
  return (
    <Series>
      <Series.Sequence
        name="AI AUDIO DUBBING"
        durationInFrames={3 * fps}
        premountFor={fps}
      >
        <PodcastOpening />
      </Series.Sequence>
      <Series.Sequence
        name="Original English · two speakers"
        durationInFrames={Math.ceil((p.tracks[0].end + 0.35) * fps)}
        premountFor={fps}
      >
        <PodcastTake index={0} />
      </Series.Sequence>
      <Series.Sequence
        name="Korean · same exchange"
        durationInFrames={Math.ceil((p.tracks[1].end + 0.35) * fps)}
        premountFor={fps}
      >
        <PodcastTake index={1} />
      </Series.Sequence>
      <Series.Sequence
        name="Japanese · same exchange"
        durationInFrames={Math.ceil((p.tracks[2].end + 0.35) * fps)}
        premountFor={fps}
      >
        <PodcastTake index={2} />
      </Series.Sequence>
      <Series.Sequence
        name="Chinese · same exchange"
        durationInFrames={Math.ceil((p.tracks[3].end + 0.35) * fps)}
        premountFor={fps}
      >
        <PodcastTake index={3} />
      </Series.Sequence>
      <Series.Sequence
        name="Korean · complete longer answer"
        durationInFrames={Math.ceil(
          (p.extended.end - p.extended.start + 0.35) * fps,
        )}
        premountFor={fps}
      >
        <PodcastTake extended />
      </Series.Sequence>
      <Series.Sequence
        name="Actual studio and product"
        durationInFrames={7 * fps}
        premountFor={fps}
      >
        <PodcastStudio />
      </Series.Sequence>
    </Series>
  );
};
