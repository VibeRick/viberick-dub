"""Snapshot actual podcast outputs for editable proof; never generates speech."""
import hashlib,json,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];run=ROOT/'runs/podcast-demo-2026-10-11';out=HERE/'public/podcast';out.mkdir(parents=True,exist_ok=True)
units=json.loads((run/'units.json').read_text());report=json.loads((run/'out/report.json').read_text())
browser_source=run/'source-browser.mp4'
if browser_source.exists():shutil.copy2(browser_source,out/'source.mp4')
else:subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(run/'source.mp4'),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out/'source.mp4')],check=True)
for name,sec in [('lex',2),('demis',7)]:subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(sec),'-i',str(out/'source.mp4'),'-frames:v','1',str(out/f'{name}.jpg')],check=True)
def audio(src,name,start,end):
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(src),'-t',str(end-start),'-vn','-c:a','aac','-b:a','192k',str(out/name)],check=True);return f'podcast/{name}'
tracks=[]
for code,label in [('en','Original English'),('ko','Korean'),('ja','Japanese'),('zh-Hans','Chinese')]:
 if code=='en':rows=[dict(u,sourceText=u['text']) for u in units];src=run/'source.mp4'
 else:
  rows=json.loads((run/'dub'/f'{code}.json').read_text())['rows'];placements=json.loads((run/'out'/f'timeline.{code}.json').read_text());byid={r['id']:r for r in placements};rows=[dict(r,**{k:byid[r['id']][k] for k in ['start','end','spk']},sourceText=next(u['text'] for u in units if u['id']==r['id'])) for r in rows];src=run/'out'/f'dub.{code}.m4a'
 pair=[r for r in rows if r['id'] in [0,1]];end=max(r['end'] for r in pair)
 if end>11.45+.01:raise ValueError('First pair overlaps the next sentence; choose a new clip boundary')
 tracks.append({'lang':code,'name':label,'audio':audio(src,f'pair.{code}.m4a',0,end),'start':0,'end':end,'rows':pair})
 if code=='ko':
  last=next(r for r in rows if r['id']==5);prior=next(r for r in rows if r['id']==4)
  if prior['end']>last['start']:raise ValueError('Extended answer starts with another speaker; isolate carefully')
  extended={'lang':code,'name':'Korean · full answer','audio':audio(src,'answer.ko.m4a',last['start'],last['end']),'start':last['start'],'end':last['end'],'rows':[last]}
p={'ready':True,'run':run.name,'source':'podcast/source.mp4','lexImage':'podcast/lex.jpg','demisImage':'podcast/demis.jpg','sourceCredit':'Lex Fridman Podcast #475 · Demis Hassabis','sourceOffset':3387,'alignment':'Source turns aligned from audio against the published transcript; not an automatic diarization benchmark.','tracks':tracks,'extended':extended,'report':report,'studio':None}
shot=ROOT/'docs/review-2026-10-10/podcast-studio.jpg'
if shot.exists():shutil.copy2(shot,out/'studio.jpg');p['studio']='podcast/studio.jpg'
p['originalSourceSha256']=hashlib.sha256((run/'source.mp4').read_bytes()).hexdigest()
p['browserSourceSha256']=hashlib.sha256((out/'source.mp4').read_bytes()).hexdigest()
p['hashes']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file() and f.name!='manifest.json'}
(out/'manifest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2));(HERE/'src/podcast.json').write_text(json.dumps(p,ensure_ascii=False,indent=2));print('Podcast proof snapshot ready; full utterances retained.')
