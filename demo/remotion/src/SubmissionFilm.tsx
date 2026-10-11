import { Audio } from "@remotion/media";
import { AbsoluteFill, Img, OffthreadVideo, Series, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import script from "./submission-script.json";
import podcast from "./podcast.json";
import { VoiceReveal } from "./LaunchOpening";

type SceneName = keyof typeof script;
const ink = "#17263a", paper = "#eef2f7", blue = "#265fb0";
const titles: Record<SceneName, string> = {
  problem: "One video. The work repeats.", product: "Your video in more languages.",
  conversation: "Two speakers. A new audience.", pipeline: "Translate for the time. Check the result.",
  repair: "The system listens back.", voice: "And it can still sound like you.",
  architecture: "Built to finish the job.", finish: "You made the video.\nWe handle the languages.",
};
export const SubmissionScene = ({name = "problem"}: {name?: SceneName}) => {
 const frame = useCurrentFrame(), {fps} = useVideoConfig();
 const copy = script[name];
 const narrationAudio = copy.audio as string | null;
 const words = copy.text.split(" ");
 const chunks = Array.from({length:Math.ceil(words.length/13)},(_,i)=>words.slice(i*13,(i+1)*13).join(" "));
 const chunk = Math.min(chunks.length-1, Math.floor(frame / Math.max(1,copy.frames/chunks.length)));
 return <AbsoluteFill style={{background:paper,color:ink,fontFamily:"Arial, sans-serif",padding:"58px 86px"}}>
  <div style={{fontSize:28,display:"flex",justifyContent:"space-between"}}><b>VibeRick Dub</b><span style={{color:blue}}>{narrationAudio ? "Product walkthrough" : "Product walkthrough · narration pending"}</span></div>
  {narrationAudio && <Audio src={staticFile(narrationAudio)} premountFor={fps}/>}
  <h1 style={{fontSize:72,lineHeight:1.1,letterSpacing:"-2px",maxWidth:1640,margin:"42px 0 34px",whiteSpace:"pre-line"}}>{titles[name]}</h1>
  {(name === "product" || name === "finish") ? <div style={{display:"flex",gap:80,height:600}}>
    <Img src={staticFile("evidence/outcome-studio.jpg")} style={{width:550,height:600,objectFit:"contain",objectPosition:"top"}}/>
    <div style={{fontSize:44,lineHeight:1.5,paddingTop:30}}><p>Dubbed video</p><p>Audio tracks</p><p>Synced subtitles</p><div style={{fontSize:26,color:blue,marginTop:40}}>Actual local interface · four tested pipeline languages</div></div>
  </div> : name === "problem" ? <div style={{display:"flex",gap:30,marginTop:100}}>{["Translate","Record","Match timing","Build subtitles"].map((label,i)=><div key={label} style={{flex:1,borderTop:`5px solid ${blue}`,paddingTop:30}}><div style={{fontSize:24,color:blue}}>Step {i+1}</div><div style={{fontSize:44,marginTop:22}}>{label}</div></div>)}</div>
  : name === "pipeline" ? <div style={{marginTop:65}}>{["Chirp: words + timestamps","Gemini: timed translation + speech","Measure → listen → retry or flag"].map((label,i)=><div key={label} style={{fontSize:48,borderBottom:"1px solid #c2cfdf",padding:"26px 0",color:frame / fps > i*3 ? ink : "#73849a"}}>{label}</div>)}</div>
  : name === "repair" ? <div style={{marginTop:55}}><p style={{fontSize:26,color:blue}}>Actual archived creator run · Japanese line 14</p>{["Checker: spoken in Korean instead of Japanese","Action: generate another take","Next automated check: passed"].map((label,i)=><div key={label} style={{fontSize:43,padding:"27px 0",borderBottom:"1px solid #c2cfdf",opacity:frame/fps >= i*2 ? 1 : .25}}>{label}</div>)}<p style={{fontSize:25,color:"#425570"}}>This model verdict is not human listening certification.</p></div>
  : name === "architecture" ? <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:44,marginTop:60}}>{[["Firebase Hosting","The creator’s workspace"],["Firestore","Progress and line results"],["Cloud Run","API and independent workers"],["Cloud Storage","Source and completed media"]].map(([title,description])=><div key={title} style={{borderLeft:`5px solid ${blue}`,paddingLeft:30}}><h2 style={{fontSize:44,margin:"0 0 14px"}}>{title}</h2><p style={{fontSize:30,color:"#425570",margin:0}}>{description}</p></div>)}</div>
  : <div style={{fontSize:56,lineHeight:1.4,marginTop:100,maxWidth:1300}}>{name === "voice" ? "Original Korean → consented English voice" : "Original English → Korean audio + subtitles"}<p style={{fontSize:30,color:blue}}>{name === "voice" ? "A separate creator recording; not the podcast speakers." : "Distinct AI presets · transcript-assisted source alignment"}</p></div>}
  <div style={{position:"absolute",bottom:38,left:86,right:86,padding:"18px 24px",background:ink,color:"white",fontSize:32,lineHeight:1.4}}>{chunks[chunk]}</div>
 </AbsoluteFill>;
};

export const ConversationProof = ({index = 0, reply = false}: {index?: number; reply?: boolean}) => {
 const {fps}=useVideoConfig(), sec=useCurrentFrame()/fps, track=podcast.tracks[index];
 const offset = reply ? 5.34 : 0;
 const row=track.rows.find(r=>sec+offset>=r.start&&sec+offset<r.end);
 return <AbsoluteFill style={{background:paper,color:ink,fontFamily:"Arial, Noto Sans KR, sans-serif",padding:"55px 86px"}}>
  <div style={{fontSize:29,display:"flex",justifyContent:"space-between"}}><b>VibeRick Dub</b><span>Local review · footage permission pending</span></div>
  <h1 style={{fontSize:68,margin:"36px 0"}}>{index===0?"Original English":"Korean dub"}</h1>
  <div style={{display:"flex",gap:45}}><OffthreadVideo src={staticFile(podcast.source)} trimBefore={Math.round(offset * fps)} muted style={{width:1180,height:664,objectFit:"contain",borderRadius:14}}/>
   <div style={{fontSize:32,paddingTop:90,lineHeight:1.6}}><b>Lex Fridman</b><p style={{margin:"0 0 45px",color:blue}}>{index===0?"Original speaker":"Charon preset"}</p><b>Demis Hassabis</b><p style={{margin:0,color:blue}}>{index===0?"Original speaker":"Algieba preset"}</p></div>
  </div>
  <p style={{fontSize:39,lineHeight:1.35,margin:"24px 0 0",minHeight:105}}>{row?.text || ""}</p>
  <Audio src={staticFile(track.audio)} trimBefore={Math.round(offset * fps)} premountFor={fps}/>
 </AbsoluteFill>;
};

export const submissionFrames = Object.values(script).reduce((n,row)=>n+row.frames,0)+157+156+156+140+138;
export const SubmissionFilm = () => {
 const {fps}=useVideoConfig();
 return <Series>
  <Series.Sequence name="Hear the original immediately" durationInFrames={157} premountFor={fps}><ConversationProof index={0}/></Series.Sequence>
  <Series.Sequence name="Hear the Korean result" durationInFrames={156} premountFor={fps}><ConversationProof index={1}/></Series.Sequence>
  <Series.Sequence name="The repeated work" durationInFrames={script.problem.frames} premountFor={fps}><SubmissionScene name="problem"/></Series.Sequence>
  <Series.Sequence name="The product" durationInFrames={script.product.frames} premountFor={fps}><SubmissionScene name="product"/></Series.Sequence>
  <Series.Sequence name="Conversation setup" durationInFrames={script.conversation.frames} premountFor={fps}><SubmissionScene name="conversation"/></Series.Sequence>
  <Series.Sequence name="The second speaker replies" durationInFrames={156} premountFor={fps}><ConversationProof index={1} reply/></Series.Sequence>
  <Series.Sequence name="Timed translation and checking" durationInFrames={script.pipeline.frames} premountFor={fps}><SubmissionScene name="pipeline"/></Series.Sequence>
  <Series.Sequence name="Recorded automatic repair" durationInFrames={script.repair.frames} premountFor={fps}><SubmissionScene name="repair"/></Series.Sequence>
  <Series.Sequence name="Creator voice setup" durationInFrames={script.voice.frames} premountFor={fps}><SubmissionScene name="voice"/></Series.Sequence>
  <Series.Sequence name="Creator original" durationInFrames={140} premountFor={fps}><VoiceReveal index={0}/></Series.Sequence>
  <Series.Sequence name="Creator English" durationInFrames={138} premountFor={fps}><VoiceReveal index={1}/></Series.Sequence>
  <Series.Sequence name="Google architecture" durationInFrames={script.architecture.frames} premountFor={fps}><SubmissionScene name="architecture"/></Series.Sequence>
  <Series.Sequence name="Finished files" durationInFrames={script.finish.frames} premountFor={fps}><SubmissionScene name="finish"/></Series.Sequence>
 </Series>;
};

export const productFrames = 157 + 156 + script.product.frames + 140 + 138 + script.finish.frames;
export const ProductFilm = () => {
 const {fps} = useVideoConfig();
 return <Series>
  <Series.Sequence name="Original interview line" durationInFrames={157} premountFor={fps}><ConversationProof index={0}/></Series.Sequence>
  <Series.Sequence name="Dubbed interview line" durationInFrames={156} premountFor={fps}><ConversationProof index={1}/></Series.Sequence>
  <Series.Sequence name="Automatic multilingual outputs" durationInFrames={script.product.frames} premountFor={fps}><SubmissionScene name="product"/></Series.Sequence>
  <Series.Sequence name="Consented creator original" durationInFrames={140} premountFor={fps}><VoiceReveal index={0}/></Series.Sequence>
  <Series.Sequence name="Consented creator English" durationInFrames={138} premountFor={fps}><VoiceReveal index={1}/></Series.Sequence>
  <Series.Sequence name="Download and finish" durationInFrames={script.finish.frames} premountFor={fps}><SubmissionScene name="finish"/></Series.Sequence>
 </Series>;
};
