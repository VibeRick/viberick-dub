"""Inspect the four authorized local narration takes and fit the scene durations."""
import json, math, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
config={'enabled':True}
for scene in ['opening','studio','evidence','closing']:
 path=root/'public/narration'/f'{scene}.wav'
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True))
 if duration<=0: raise ValueError(f'Empty narration: {scene}')
 config[scene]={'file':f'narration/{scene}.wav','duration':math.ceil((duration+.35)*30)/30,'audioDuration':duration}
e=json.loads((root/'src/evidence.json').read_text())
frames=sum(round(config[s]['duration']*30) for s in ['opening','studio','evidence','closing'])+sum(math.ceil((t['end']-e['offset']+.35)*30) for t in e['tracks'])
if frames>165*30: raise ValueError('Film exceeds the 165-second preview limit')
(root/'src/narration.json').write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps({'scenes':config,'filmSeconds':frames/30},indent=2))
