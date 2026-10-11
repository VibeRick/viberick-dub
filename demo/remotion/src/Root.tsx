import { Composition, Folder } from "remotion";
import { Film, filmFrames, SCENES } from "./film/Film";

// The submission film, plus one composition per scene for quick previews.
export const RemotionRoot = () => (
  <>
    <Composition id="VibeRickDubFilm" component={Film} width={1920} height={1080} fps={30} durationInFrames={filmFrames} defaultProps={{}} />
    <Folder name="FilmScenes">
      {SCENES.map(s => <Composition key={s.id} id={`Film-${s.id}`} component={Film} width={1920} height={1080} fps={30} durationInFrames={s.frames} defaultProps={{ only: s.id }} />)}
    </Folder>
  </>
);
