import { SubmissionFilm, SubmissionScene, ConversationProof, submissionFrames, ProductFilm, productFrames } from "./SubmissionFilm";
import { LaunchOpening, LaunchPromise, VoiceReveal } from "./LaunchOpening";
import { StudioDemo } from "./StudioDemo";
import { PodcastOverviewDraft } from "./PodcastOverviewDraft";
import { PodcastLong } from "./PodcastLong";
import podcast from "./podcast.json";
import { PodcastTake } from "./PodcastTake";
import { PodcastStudio } from "./PodcastStudio";
import { PodcastSource } from "./Podcast";
import { PodcastOpening } from "./PodcastOpening";
import n from "./narration.json";
import e from "./evidence.json";
import { Composition, Folder } from "remotion";
import { Film, filmFrames, SCENES } from "./film/Film";
import { Demo } from "./Composition";
import { Opening } from "./Opening";
import { Proof } from "./Proof";
import { Studio } from "./Studio";
import { Evidence } from "./Evidence";
import { Closing } from "./Closing";
export const RemotionRoot = () => (
  <>
    <Composition id="VibeRickDubFilm" component={Film} width={1920} height={1080} fps={30} durationInFrames={filmFrames} defaultProps={{}} />
    <Folder name="FilmScenes">
      {SCENES.map(s => <Composition key={s.id} id={`Film-${s.id}`} component={Film} width={1920} height={1080} fps={30} durationInFrames={s.frames} defaultProps={{ only: s.id }} />)}
    </Folder>
    <Composition id="VibeRickDubProductDraft" component={ProductFilm} width={1920} height={1080} fps={30} durationInFrames={productFrames}/>
    <Composition id="VibeRickDubSubmissionDraft" component={SubmissionFilm} width={1920} height={1080} fps={30} durationInFrames={submissionFrames}/>
    <Folder name="SubmissionScenes">
      <Composition id="SubmissionProduct" component={SubmissionScene} defaultProps={{name: "product" as const}} width={1920} height={1080} fps={30} durationInFrames={380}/>
      <Composition id="SubmissionConversation" component={ConversationProof} defaultProps={{index:1}} width={1920} height={1080} fps={30} durationInFrames={318}/>
    </Folder>
    <Composition id="VibeRickDubLaunchOpening" component={LaunchOpening} width={1920} height={1080} fps={30} durationInFrames={532} />
    <Folder name="LaunchScenes">
      <Composition id="CreatorVoiceReveal" component={VoiceReveal} defaultProps={{index: 0}} width={1920} height={1080} fps={30} durationInFrames={140} />
      <Composition id="LaunchPromise" component={LaunchPromise} width={1920} height={1080} fps={30} durationInFrames={120} />
    </Folder>
    <Composition
      id="VibeRickDubPodcast"
      component={StudioDemo}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={840}
    />
    <Composition
      id="PodcastOverviewDraft"
      component={PodcastOverviewDraft}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={720}
    />
    <Composition
      id="PodcastLongDraft"
      component={PodcastLong}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={2179}
    />
    <Composition
      id="PodcastOpening"
      component={PodcastOpening}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={90}
    />
    <Composition
      id="PodcastOriginal"
      calculateMetadata={() => ({
        durationInFrames: Math.ceil((podcast.tracks[0].end + 0.35) * 30),
      })}
      component={PodcastSource}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={354}
    />
    <Composition
      id="PodcastKorean"
      component={PodcastTake}
      defaultProps={{ index: 1, extended: false }}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={317}
    />
    <Composition
      id="PodcastStudio"
      component={PodcastStudio}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={210}
    />
    <Folder name="Archive">
      <Composition
        id="VibeRickDubReview"
        calculateMetadata={() => ({
          durationInFrames:
            Math.ceil(n.opening.duration * 30) +
            Math.ceil(n.studio.duration * 30) +
            Math.ceil(n.evidence.duration * 30) +
            Math.ceil(n.closing.duration * 30) +
            e.tracks.reduce(
              (sum, t) => sum + Math.ceil((t.end - e.offset + 0.35) * 30),
              0,
            ),
        })}
        component={Demo}
        width={1920}
        height={1080}
        fps={30}
        durationInFrames={2400}
      />
      <Folder name="Scenes">
        <Composition
          id="Opening"
          calculateMetadata={() => ({
            durationInFrames: Math.ceil(n.opening.duration * 30),
          })}
          component={Opening}
          width={1920}
          height={1080}
          fps={30}
          durationInFrames={240}
        />
        <Composition
          id="FourLanguageProof"
          calculateMetadata={() => ({
            durationInFrames: e.tracks.reduce(
              (sum, t) => sum + Math.ceil((t.end - e.offset + 0.35) * 30),
              0,
            ),
          })}
          component={Proof}
          width={1920}
          height={1080}
          fps={30}
          durationInFrames={960}
        />
        <Composition
          id="Studio"
          calculateMetadata={() => ({
            durationInFrames: Math.ceil(n.studio.duration * 30),
          })}
          component={Studio}
          width={1920}
          height={1080}
          fps={30}
          durationInFrames={420}
        />
        <Composition
          id="RecordedRepair"
          calculateMetadata={() => ({
            durationInFrames: Math.ceil(n.evidence.duration * 30),
          })}
          component={Evidence}
          width={1920}
          height={1080}
          fps={30}
          durationInFrames={360}
        />
        <Composition
          id="Architecture"
          calculateMetadata={() => ({
            durationInFrames: Math.ceil(n.closing.duration * 30),
          })}
          component={Closing}
          width={1920}
          height={1080}
          fps={30}
          durationInFrames={420}
        />
      </Folder>
    </Folder>
  </>
);
