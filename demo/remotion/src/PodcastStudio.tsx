import { AbsoluteFill, Img, staticFile } from "remotion";
import p from "./podcast.json";
export const PodcastStudio = () => {
  return (
    <AbsoluteFill
      style={{
        background: "#080f1b",
        color: "white",
        fontFamily: "Arial,sans-serif",
        padding: 85,
      }}
    >
      <div style={{ fontSize: 45, fontWeight: 800 }}>AI AUDIO DUBBING</div>
      <h1 style={{ fontSize: 86, letterSpacing: -3, margin: "55px 0 35px" }}>
        Review every speaker.
        <br />
        Switch every track.
      </h1>
      {p.studio ? (
        <Img
          src={staticFile(p.studio)}
          style={{
            position: "absolute",
            right: 90,
            top: 200,
            width: 760,
            height: 660,
            objectFit: "contain",
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: 90,
          bottom: 160,
          fontSize: 55,
          color: "#8ab9ff",
        }}
      >
        viberick-dub.web.app
      </div>
      <div
        style={{
          position: "absolute",
          left: 94,
          bottom: 95,
          fontSize: 27,
          color: "#aab8cb",
        }}
      >
        VibeRick Dub · Local review build · AI preset dubbing
      </div>
    </AbsoluteFill>
  );
};
