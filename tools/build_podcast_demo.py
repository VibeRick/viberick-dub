"""Build the approved 40-second Lex/Demis preset-voice proof from local source only."""
import json
import os
from pathlib import Path
import shutil
import time

from google.genai import types
from dub import config, events, gem, pipeline, review, subs
from dub.budget import Budget
from dub.quality import audit_run
from tools.validate_voice import fingerprint, guarded_requests

RUN = Path('runs/podcast-demo-2026-10-11')
SPEAKERS = {'lex': {'name': 'Lex Fridman', 'voice': 'Charon', 'voice_type': 'preset'},
            'demis': {'name': 'Demis Hassabis', 'voice': 'Algieba', 'voice_type': 'preset'}}
TEXTS = [
    ('lex', 0, 5, 'Yeah, something like a new conjecture or scientific discovery. That would be a cool feeling.'),
    ('demis', 5, 11, "Yeah, that would be amazing. So it’s not just helping us do that, but actually coming up with something brand new."),
    ('lex', 11, 13, 'And you would be in the room for that.'),
    ('demis', 13, 13.7, 'Absolutely.'),
    ('lex', 13, 22, 'It would be probably two or three months before announcing it. And you would just be sitting there trying not to Tweet.'),
    ('demis', 22, 40, 'Something like that. Exactly. It’s like what is this amazing new physics idea? And then we would probably check it with world experts in that domain and validate it and go through its workings. And I guess it would be explaining its workings too. Yeah. It would be an amazing moment.'),
]


def main():
    keys = [os.environ.get(k) for k in ('GEMINI_API_KEY', 'GEMINI_TTS_API_KEY')]
    if not all(keys) or gem._client is not None:
        raise RuntimeError('Fresh process with explicit VibeRick environment keys required')
    if (RUN / 'out/report.json').exists():
        raise RuntimeError('Existing completed run must not be regenerated')
    budget = Budget(100, {'tts': 500, 'text': 500}, ledger_path=Path('runs/validation-budget-2026-10-10.json'), run_cap_usd=20)
    old_keys = config.gemini_key, config.tts_key
    evidence = {}
    started = time.time()
    info = {'id': '-HzgcbRXUK8', 'title': 'Demis Hassabis × Lex Fridman — new scientific discoveries',
            'channel': 'Lex Fridman', 'duration': 40.0, 'src': 'en', 'speakers': SPEAKERS,
            'source_url': 'https://www.youtube.com/watch?v=-HzgcbRXUK8&t=3387s',
            'transcript_url': 'https://lexfridman.com/demis-hassabis-2-transcript',
            'source_interval': {'start': 3387, 'end': 3427}, 'source_captioned': False,
            'caption_evidence': 'Visual inspection of source frame; no burned captions.',
            'voice_disclosure': 'AI preset dubbing. Charon portrays Lex; Algieba portrays Demis. These are not cloned voices.',
            'rights_status': 'Source attribution recorded; permission for public redistribution not established.'}
    brief = {'summary': 'Two-person podcast exchange imagining AI making a new scientific discovery, then experts checking and validating it.',
             'speaker_style': 'Conversational interview. Preserve the short back-and-forth, humor and uncertainty. Two distinct preset voices, never impersonation.',
             'terms': [{'source': 'conjecture', 'rule': 'Use the target-language term for a scientific conjecture or hypothesis.'},
                       {'source': 'Tweet', 'rule': 'Use the ordinary target-language verb for posting on Twitter/X.'}]}
    (RUN / 'info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2))
    (RUN / 'cast.json').write_text(json.dumps(SPEAKERS, indent=2))
    (RUN / 'brief.json').write_text(json.dumps(brief, indent=2))
    plan = {'source': fingerprint(RUN / 'source.mp4'), 'audio': fingerprint(RUN / 'source.wav'),
            'tool': fingerprint(Path(__file__)), 'code': [fingerprint(Path('dub') / f'{n}.py') for n in ('agent','translate','voice','check','mix','pipeline')],
            'source_attribution': info['source_url'], 'voice_disclosure': info['voice_disclosure'],
            'budget': {'global': 100, 'trial': 20, 'per_attempt_allowance': .2, 'kind': 'estimated spending stop'}}
    (RUN / 'production-plan.json').write_text(json.dumps(plan, indent=2))
    try:
        config.gemini_key, config.tts_key = lambda: keys[0], lambda: keys[1]
        with guarded_requests(budget, .2, .2) as evidence:
            alignment = gem.json_call(
                'Listen to this exact 40-second English interview clip. Match the SIX official transcript turns below to audible speech. '
                'Return each id once with start/end in clip-relative seconds at the actually audible phrase boundaries. '
                'Do not infer speaker identity from sound; names/turns are supplied by the official transcript. '
                'The brief Absolutely overlaps or precedes the next Lex turn: preserve it with its own times, allow overlap. '
                'Also report whether two different source voices are audible. Do not omit words or fabricate timings beyond40s. '
                + json.dumps([{'id': i, 'speaker': t[0], 'rough_start': t[1], 'text': t[3]} for i,t in enumerate(TEXTS)]),
                {'type':'object','properties':{'two_distinct_voices_audible':{'type':'boolean'},'evidence':{'type':'string'},
                 'turns':{'type':'array','items':{'type':'object','properties':{'id':{'type':'integer'},'start':{'type':'number'},'end':{'type':'number'}},'required':['id','start','end']}}},
                 'required':['two_distinct_voices_audible','evidence','turns']},
                parts=[types.Part.from_bytes(data=(RUN/'source.wav').read_bytes(), mime_type='audio/wav')])
            if not alignment['two_distinct_voices_audible'] or sorted(t['id'] for t in alignment['turns']) != list(range(6)):
                raise RuntimeError('Source alignment did not confirm expected two-speaker six-turn clip')
            positions = {t['id']: t for t in alignment['turns']}
            units = []
            for i, (speaker, rough_start, rough_end, text) in enumerate(TEXTS):
                p = positions[i]
                if not 0 <= p['start'] < p['end'] <= 40 or abs(p['start']-rough_start)>2:
                    raise RuntimeError('Source alignment outside expected official transcript timing; review needed')
                units.append({'id':i, 'start':p['start'], 'end':p['end'], 'slot':round(p['end']-p['start'],3),
                              'text':text, 'spk':speaker, 'voice':SPEAKERS[speaker]['voice'], 'hard_anchor':True})
            (RUN/'source-alignment.json').write_text(json.dumps({'method':'Gemini audio-estimated timings against official transcript, not forced alignment','result':alignment},indent=2))
            (RUN/'units.json').write_text(json.dumps(units,ensure_ascii=False,indent=2))
            print('SOURCE_TIMINGS_READY '+json.dumps([{'id':u['id'],'spk':u['spk'],'start':u['start'],'end':u['end']} for u in units]),flush=True)
            out=RUN/'out';out.mkdir(exist_ok=True)
            shutil.copy2(RUN/'source.mp4',out/'video.orig.mp4')
            srt=subs.srt(units,[u['text'] for u in units],'en')
            (out/'subs.en.srt').write_text(srt);(out/'subs.en.vtt').write_text(subs.vtt(srt))
            events.log(RUN,'start',title=info['title'],url=info['source_url'],speakers=SPEAKERS)
            reports, failures = pipeline._languages(RUN, units, 'en', ['ko','ja','zh-Hans'], brief,40.,None)
            summary={'video':info['id'],'title':info['title'],'src':'en','duration':40.,'units':len(units),
                     'langs':reports,'failures':failures,'speakers':SPEAKERS,'voice_disclosure':info['voice_disclosure'],
                     'source_captioned':False,'sec_total':round(time.time()-started,2),'gemini_text_usd':gem.cost()}
            (out/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
            review.write(RUN,RUN/'source.wav',units,[r['lang'] for r in reports])
            (RUN/'quality-audit.json').write_text(json.dumps(audit_run(RUN),indent=2))
            print(json.dumps(summary),flush=True)
    finally:
        config.gemini_key,config.tts_key=old_keys
        (RUN/'production-budget.json').write_text(json.dumps({**budget.snapshot(),'usage_evidence':evidence},indent=2))


if __name__=='__main__':
    main()
