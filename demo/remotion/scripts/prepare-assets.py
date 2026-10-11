"""Copy a reproducible, local-only evidence snapshot; no network or generation."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]; ROOT=HERE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--review',type=Path,default=ROOT/'web/review');p.add_argument('--run',type=Path,default=ROOT/'runs/Fty2sz3dBwU.180s');p.add_argument('--events-run',type=Path);p.add_argument('--unit',type=int,default=1);p.add_argument('--label',default='Recorded baseline · revised local mix');a=p.parse_args()
source_units=json.loads((a.run/'units.json').read_text());unit=source_units[a.unit];timelines={lang:json.loads((a.review/f'timeline.{lang}.json').read_text())[a.unit] for lang in ['en','ja','zh-Hans']};offset=min(unit['start'],*(v['start'] for v in timelines.values()))
out=HERE/'public/evidence';out.mkdir(parents=True,exist_ok=True)
def clip(src,name,end,video=False,start=None):
 start=offset if start is None else start
 if end-offset>8.001: raise ValueError("Selected phrase exceeds the prepared video window")
 target=out/name
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(src)]
 cmd+=['-t',str(end-offset),'-an','-vf','scale=1280:-2','-c:v','libx264','-crf','21','-preset','fast'] if video else ['-vn','-af',f'atrim=duration={end-start},asetpts=PTS-STARTPTS,adelay={round((start-offset)*1000)}:all=1','-c:a','aac','-b:a','192k']
 subprocess.run(cmd+[str(target)],check=True)
 return 'evidence/'+name
source_video=next(f for f in [a.review/'video.clean.orig.mp4',a.review/'video.orig.mp4',a.run/'source.mp4'] if f.exists())
manifest={'label':a.label,'run':a.run.name,'tracks':[],'report':json.loads((a.review/'report.json').read_text())}
manifest['video']=clip(source_video,'source.mp4',offset+8,True)
manifest['offset']=offset;manifest['unit']=a.unit
manifest['sourceStart']=unit['start'];manifest['sourceText']=unit['text'];manifest['sourceSlot']=unit['slot']
manifest['tracks'].append({'lang':'ko','name':'Original Korean','text':unit['text'],'start':unit['start'],'end':unit['end'],'audio':clip(source_video,'ko.m4a',unit['end'],start=unit['start'])})
for lang,name in [('en','English'),('ja','Japanese'),('zh-Hans','Chinese')]:
 row=timelines[lang]
 dub=json.loads((a.run/'dub'/f'{lang}.json').read_text());transcript=next(r['text'] for r in dub['rows'] if r['id']==unit['id'])
 manifest['tracks'].append({'lang':lang,'name':name,'text':transcript,'start':row['start'],'end':row['end'],'audio':clip(a.review/f'dub.{lang}.m4a',lang+'.m4a',row['end'],start=row['start']),'interval':row})
event_run=a.events_run or a.run;manifest['eventRun']=event_run.name
events=[json.loads(line) for line in (event_run/'events.jsonl').read_text().splitlines()]
failed=next((e for e in events if e.get('lang')=='ja' and e.get('ok') is False),None)
manifest['events']=[e for e in events if failed and e.get('lang')=='ja' and e.get('id')==failed.get('id')]
shot=ROOT/'docs/review-2026-10-10/studio-refined-desktop.jpg';shutil.copy2(shot,out/'studio.jpg');manifest['studio']='evidence/studio.jpg'
manifest['hashes']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file() and f.name!='manifest.json'}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(HERE/'src/evidence.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps({'run':manifest['run'],'tracks':[{k:t[k] for k in ['lang','end']} for t in manifest['tracks']],'events':len(manifest['events'])}))
