"""Regression checks for owner-preview recovery and offline recorded review boundaries."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="Node is needed for browser helper tests")
def test_preview_recovery_and_recorded_manifest_boundaries():
    source = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    helpers = "\n".join(
        re.search(rf"(?:async )?function {name}\([^\n]*\) \{{[\s\S]*?\n\}}", source).group()
        for name in ["mergeRecoveredPreview", "loadRecordedManifest", "failedAudioAttempts", "canAcceptPreview", "lineActionLabel", "evText", "canonicalCreateBody", "parsePendingCreate", "makePendingCreate", "createFromBody", "lineChanges", "timelineChange", "speakerIdentity"]
    )
    script = helpers + r'''
const assert=require('node:assert/strict');
assert.equal(speakerIdentity({spk:'a'},{a:{name:'Speaker Alice',voice_type:'preset'}}).name,'Speaker Alice');
assert.equal(speakerIdentity({spk:0},[{id:0,name:'Speaker Zero'}]).name,'Speaker Zero');
assert.equal(speakerIdentity({spk:'unknown'},{}).name,'Speaker unknown');
assert.equal(speakerIdentity({},{}),null);
const refined={ok:true,actions:[{do:'lengthen'},{do:'check',ok:true}]};
assert.equal(lineChanges(refined).timing,true);
assert.equal(lineChanges(refined).recovered,false);
assert.equal(timelineChange(refined,false).label,'timing refined');
const recovered={ok:true,actions:[{do:'check',ok:false},{do:'resynth'},{do:'check',ok:true}]};
assert.equal(lineChanges(recovered).recovered,true);
assert.deepEqual(timelineChange(recovered,true),{className:'',label:''});
assert.deepEqual(timelineChange(refined,true),{className:'',label:''});
assert.equal(lineChanges({ok:false,actions:[{do:'check',ok:false}]}).recovered,false);
const canonical=canonicalCreateBody(' https://youtu.be/test ',['ja','en','en']);
assert.equal(canonical,JSON.stringify({url:'https://youtu.be/test',langs:['en','ja']}));
const pending=makePendingCreate(canonical,null,()=> 'request-one',()=>new Uint8Array(32).fill(170));
assert.equal(pending.ownerToken.length,64);
assert.equal(parsePendingCreate(JSON.stringify(pending)).ownerToken,pending.ownerToken);
assert.equal(parsePendingCreate(JSON.stringify({...pending,ownerToken:'short'})),null);
assert.equal(makePendingCreate(canonical,pending,()=>{throw Error('must reuse')},()=>{throw Error('must reuse')}),pending);
assert.notEqual(makePendingCreate(canonicalCreateBody('https://youtu.be/new',['en']),pending,()=> 'request-two',()=>new Uint8Array(32).fill(171)).key,pending.key);
const recordedMode=false;
const PENDING_CREATE_KEY='pending';
let pendingCreate=null,creating=false;
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{});return elements.get(selector);};
const renderPendingCreate=()=>{};
const saved=new Map();
global.localStorage={getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)};
global.history={pushState:()=>{}};
global.open=()=>{};
global.crypto=require('node:crypto').webcrypto;
const auditions=failedAudioAttempts({actions:[
 {do:'synth',audio_key:'missing'},
 {do:'check',ok:false,audio_key:'failed.wav',text:'expected'},
 {do:'check',ok:true,audio_key:'passed.wav'},
 {do:'check',ok:false,audio_key:'unavailable.wav'}
]}, {'failed.wav':'/review/failed.wav','passed.wav':'/review/passed.wav'});
assert.equal(auditions.length,1);
assert.equal(auditions[0].attempt,1);
assert.equal(auditions[0].action.text,'expected');
assert.equal(failedAudioAttempts({actions:[{do:'check',ok:false}]},{}).length,0);
assert.equal(canAcceptPreview({status:'ready',row:{ok:false}},false),false);
assert.equal(canAcceptPreview({status:'ready',row:{ok:false}},true),true);
assert.equal(canAcceptPreview({status:'ready',row:{ok:true}},false),true);
assert.equal(canAcceptPreview({status:'running',row:{ok:true}},true),false);
assert.equal(canAcceptPreview({status:'ready'},false),false);
assert.match(lineActionLabel({do:'lengthen',text:'expanded'}),/reduce silence/);
assert.match(lineActionLabel({do:'translation_flag',issue:'wrong script'}),/wrong script/);
assert.match(evText({kind:'voice',voice:'pending_verification',consent:true})[1],/verification is pending/);
assert.doesNotMatch(evText({kind:'voice',consent:true})[1],/cloned voice/);
const edit={text:'edited',revision:2,status:'ready',lang:'en',line_id:0};
const restored=mergeRecoveredPreview({text:'original',revision:2},'edit-a',edit);
assert.equal(restored.id,'edit-a');
assert.equal(restored.text,'edited');
assert.equal(restored.preview.status,'ready');
assert.equal(mergeRecoveredPreview({id:'other',preview:{status:'running'}},'edit-a',edit),null);
assert.equal(mergeRecoveredPreview(restored,'edit-a',{...edit,status:'error'}).preview.status,'error');
global.location={href:'http://localhost:8877/?review=./review/manifest.json',origin:'http://localhost:8877'};
let result;
global.openLocal=data=>{result=data;};
let manifest={job:{outputs:{'video.en.mp4':'video.en.mp4'},can_regenerate:true},lines:{en:{rows:[]}},events:[]};
global.fetch=async()=>({ok:true,json:async()=>structuredClone(manifest)});
(async()=>{
 await assert.rejects(loadRecordedManifest('https://example.com/review/manifest.json'));
 await assert.rejects(loadRecordedManifest('./review/../app.json'));
 await assert.rejects(loadRecordedManifest('./review/manifest.json?other=1'));
 await loadRecordedManifest('./review/manifest.json');
 assert.equal(result.job.outputs['video.en.mp4'],'http://localhost:8877/review/video.en.mp4');
 assert.equal(result.job.can_regenerate,false);
 manifest.job.outputs['video.en.mp4']='https://example.com/video.mp4';
 await assert.rejects(loadRecordedManifest('./review/manifest.json'));
 let firstHeaders;
 global.fetch=async(path,options)=>{assert.ok(saved.has(PENDING_CREATE_KEY));firstHeaders=options.headers;throw Error('response lost');};
 await createFromBody(canonical);
 assert.ok(saved.has(PENDING_CREATE_KEY));
 // Simulate reload: only persisted pending material survives.
 pendingCreate=parsePendingCreate(saved.get(PENDING_CREATE_KEY));
 global.fetch=async(path,options)=>{
   assert.equal(options.headers['Idempotency-Key'],firstHeaders['Idempotency-Key']);
   assert.equal(options.headers['X-Job-Token'],firstHeaders['X-Job-Token']);
   assert.equal(options.body,canonical);
   return {ok:true,json:async()=>({id:'recovered-job',owner_token:options.headers['X-Job-Token'],replayed:true})};
 };
 await createFromBody(canonical);
 assert.equal(saved.has(PENDING_CREATE_KEY),false);
 assert.equal(saved.get('dub-token:recovered-job'),firstHeaders['X-Job-Token']);
 let called=false;
 global.localStorage.setItem=()=>{throw Error('storage unavailable')};
 global.fetch=async()=>{called=true;};
 await createFromBody(canonical);
 assert.equal(called,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run([shutil.which("node"), "-e", script], check=True, capture_output=True, text=True)


@pytest.mark.skipif(not shutil.which("node"), reason="Node is needed for browser helper tests")
def test_language_outcomes_do_not_hide_partial_or_unknown_quality():
    source = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    helper = re.search(r"function languageOutcome\([^\n]*\) \{[\s\S]*?\n\}", source).group()
    script = helper + r'''
const assert = require('node:assert/strict');
const job = {status:'running',outputs:{'video.en.mp4':'/en.mp4'},language_reports:{en:{lines:3,ok:2}}};
assert.equal(languageOutcome(job,'en').label,'Needs attention');
assert.equal(languageOutcome(job,'ja').label,'Processing');
assert.equal(languageOutcome({...job,status:'partial'},'ja').label,'Unavailable');
assert.equal(languageOutcome({...job,language_reports:{}},'en').label,'Checks unavailable');
assert.equal(languageOutcome(job,'en',{rows:[{ok:true},{ok:true},{ok:true}]}).label,'Checks passed');
assert.equal(languageOutcome(job,'en',{rows:[{ok:true},{}]}).flags,1);
assert.equal(languageOutcome({...job,report:{failures:[{lang:'ja'}]}},'ja').label,'Unavailable');
'''
    subprocess.run([shutil.which("node"), "-e", script], check=True, capture_output=True, text=True)
