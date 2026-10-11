import {
  AbsoluteFill,
  CanvasImage,
  staticFile,
  useVideoConfig,
} from "remotion";
import p from "./podcast.json";
export const PodcastOpening = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill
      style={{
        background: "#080f1b",
        fontFamily: "Arial, sans-serif",
        color: "#fff",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 62,
          left: 90,
          fontSize: 126,
          fontWeight: 800,
          letterSpacing: -5,
          zIndex: 2,
        }}
      >
        AI AUDIO <span style={{ color: "#8ab9ff" }}>DUBBING</span>
      </div>
      <CanvasImage
        src={staticFile(p.lexImage)}
        premountFor={fps}
        style={{
          position: "absolute",
          top: 245,
          left: 70,
          width: 875,
          height: 492,
          objectFit: "cover",
        }}
      />
      <CanvasImage
        src={staticFile(p.demisImage)}
        premountFor={fps}
        style={{
          position: "absolute",
          top: 245,
          left: 975,
          width: 875,
          height: 492,
          objectFit: "cover",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 762,
          left: 94,
          fontSize: 40,
          color: "#f3b96c",
        }}
      >
        Lex Fridman
      </div>
      <div
        style={{
          position: "absolute",
          top: 762,
          left: 997,
          fontSize: 40,
          color: "#8ab9ff",
        }}
      >
        Demis Hassabis
      </div>
      <div
        style={{
          position: "absolute",
          left: 94,
          top: 854,
          fontSize: 57,
          fontWeight: 600,
        }}
      >
        Two speakers. Three new languages.
      </div>
      <div
        style={{
          position: "absolute",
          left: 96,
          bottom: 58,
          fontSize: 28,
          color: "#aab8cb",
        }}
      >
        VibeRick Dub · Real interview excerpt · Two distinct AI preset voices
      </div>
    </AbsoluteFill>
  );
};
