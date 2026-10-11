import json
import wave
from pathlib import Path

import pytest

from dub import mix, pipeline, review, subs, units, voice


def clip(path, seconds, value=1000):
    import array
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(voice.RATE)
        w.writeframes((array.array('h', [value]) * int(seconds * voice.RATE)).tobytes())
    return path


def test_complete_tail_and_honest_early_metrics(tmp_path):
    cs = [clip(tmp_path/'a.wav', .3), clip(tmp_path/'b.wav', 3)]
    result = mix.place([{'start': 0}, {'start': 1}], cs, 2, tmp_path/'out.wav', [None, .1])
    assert result['early_max'] == .35
    assert result['absolute_max'] == .35
    assert result['late_max'] == 0
    assert voice.duration(tmp_path/'out.wav') == pytest.approx(3.65)
    assert result['tail_overflow'] == 1.65


def test_speaker_turns_preserve_overlap_and_never_flow(tmp_path):
    us = [{'start': 0, 'end': 2, 'spk': 'a'}, {'start': 1, 'end': 3, 'spk': 'b'}]
    flow = units.flow_gaps(us, [False]*2, [False]*2, ['Hello', 'Reply'])
    assert flow == [None, None]
    r = mix.place(us, [clip(tmp_path/'a.wav', 2), clip(tmp_path/'b.wav', 2)], 3, tmp_path/'out.wav', flow)
    assert r['starts'] == [0, 1] and r['overlap_lines'] == 1
    import array
    samples = array.array('h', voice.pcm(tmp_path/'out.wav'))
    assert samples[int(1.5*voice.RATE)] == 2000


def test_scene_anchor_does_not_flow(tmp_path):
    us = [{'start': 0, 'end': 1}, {'start': 1.1, 'end': 2, 'scene_cut': True}]
    assert units.flow_gaps(us, [False]*2, [False]*2) == [None, None]
    r = mix.place(us, [clip(tmp_path/'a.wav', .3), clip(tmp_path/'b.wav', .5)], 2, tmp_path/'out.wav', [None, 0])
    assert r['starts'][1] == 1.1


def cached_run(tmp_path):
    (tmp_path/'out').mkdir(); (tmp_path/'dub/en').mkdir(parents=True)
    (tmp_path/'info.json').write_text(json.dumps({'id': 'fixture', 'title': 'Fixture'}))
    us = [{'id': 0, 'start': 0, 'end': 1, 'slot': 1, 'text': 'source'},
          {'id': 1, 'start': 1.1, 'end': 2, 'slot': .9, 'text': 'other'}]
    rows = [{'id': i, 'text': t, 'dur': .4, 'slot': us[i]['slot'], 'tempo': 1,
             'ok': False, 'issue': 'flagged', 'actions': [{'do': 'check', 'ok': False}]} for i,t in enumerate(['First', 'Second'])]
    report = {'lang': 'en', 'sec': 10, 'lines': 2}
    for i in range(2): clip(tmp_path/f'dub/en/{i:04d}.wav', .4)
    for name, obj in [('units.json', us), ('brief.json', {}), ('dub/en.json', {'report':report, 'rows':rows}),
                      ('out/report.json', {'src':'ko','duration':2,'langs':[report],'gemini_text_usd':.1})]:
        (tmp_path/name).write_text(json.dumps(obj))
    return us


def no_paid(*a, **kw):
    raise AssertionError('paid/network path reached')


def test_offline_remix_never_repairs_flagged_rows_and_updates_subtitles(monkeypatch, tmp_path):
    us = cached_run(tmp_path)
    for owner, attr in [(pipeline.agent,'repair_line'), (pipeline.voice,'synth'), (pipeline,'prepare'),
                        (pipeline.stt,'chirp_words'), (pipeline.translate,'translate')]:
        monkeypatch.setattr(owner, attr, no_paid)
    monkeypatch.setattr(pipeline.review, 'write', lambda *a: None)
    originals = [(tmp_path/f'dub/en/{i:04d}.wav').read_bytes() for i in range(2)]
    pipeline.offline_remix(tmp_path)
    data=json.loads((tmp_path/'dub/en.json').read_text())
    assert data['rows'][1]['source_start'] == 1.1
    assert data['rows'][1]['dub_start'] == .75
    assert '00:00:00,750 --> 00:00:01,150' in (tmp_path/'out/subs.en.srt').read_text()
    assert (tmp_path/'out/timeline.en.json').exists()
    assert originals == [(tmp_path/f'dub/en/{i:04d}.wav').read_bytes() for i in range(2)]
    local = review.job_data(tmp_path, us, ['en'])
    assert local['lines']['en']['rows'][1]['start'] == .75
    assert not data['rows'][0]['ok']


def test_language_failure_keeps_success_and_calls_callback(monkeypatch, tmp_path):
    def dub(*args):
        if args[3] == 'ja': raise RuntimeError('failed')
        return {'lang':args[3]}
    monkeypatch.setattr(pipeline,'dub_language',dub)
    called=[]
    reports, failures=pipeline._languages(tmp_path, [], 'ko', ['en','ja'], {}, 2, None,
                                          lambda path,lang,r: called.append(lang))
    assert reports == [{'lang':'en'}] and failures == [{'lang':'ja','error':'RuntimeError'}]
    assert called == ['en']


def test_regeneration_touches_only_requested_line(monkeypatch, tmp_path):
    cached_run(tmp_path)
    calls=[]
    def repair(u,text,*a,**k):
        assert k.get("preserve_user_text") is True
        calls.append(u['id'])
        return {'id':u['id'],'text':text,'dur':.4,'slot':1,'tempo':1,'ok':True,'actions':[{'do':'check','ok':True}]}
    monkeypatch.setattr(pipeline.agent,'repair_line',repair)
    monkeypatch.setattr(pipeline.mix,'mix',lambda src,bed,out: out.write_bytes(b'mix'))
    pipeline.regenerate_line(tmp_path,'en',1,'Replacement')
    assert calls == [1]
    rows=json.loads((tmp_path/'dub/en.json').read_text())['rows']
    assert not rows[0]['ok'] and rows[1]['text'] == 'Replacement'
    assert rows[1]['revision_before']['text'] == 'Second'


def test_explicit_scene_boundary_survives_sentence_merge():
    us = units.make_units([{'start': 0, 'end': 1, 'text': 'unfinished'},
                           {'start': 1.1, 'end': 2, 'text': 'next', 'scene_cut': True}], 3)
    assert len(us) == 2 and us[1]['scene_cut']


def test_offline_scene_detection_finds_synthetic_hard_cut(tmp_path):
    import subprocess
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','color=black:s=320x180:d=1:r=24',
                    '-f','lavfi','-i','color=white:s=320x180:d=1:r=24',
                    '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(tmp_path/'source.mp4')], check=True)
    result = pipeline.scene_cuts(tmp_path, 2)
    assert result['status'] == 'complete'
    assert any(abs(t - 1) <= .25 for t in result['cuts'])
    assert pipeline.scene_cuts(tmp_path, 2) == result
    cues = [{'start':0,'end':.8,'text':'first'}, {'start':1.2,'end':2,'text':'second'}]
    marked = pipeline.anchor_scenes(cues, result['cuts'])
    assert marked[1]['hard_anchor'] and len(marked) == 2


def test_scene_inside_sentence_records_evidence_without_splitting():
    marked = pipeline.anchor_scenes([{'start':0,'end':3,'text':'complete sentence'}], [1.5])
    assert len(marked) == 1 and marked[0]['scene_cuts_inside'] == [1.5]
    assert not marked[0].get('hard_anchor')


def test_legacy_cache_refused_before_paid_repair(tmp_path):
    cached_run(tmp_path)
    clip(tmp_path/'source.wav', .1)
    with pytest.raises(ValueError, match='offline-remix'):
        pipeline.guard_cache(tmp_path)
    assert not (tmp_path/'cache-identity.json').exists()


def test_cache_identity_rejects_regrouped_units_source_and_voice(monkeypatch, tmp_path):
    clip(tmp_path/'source.wav', .1)
    us=[{'id':0,'start':0,'end':1,'text':'first','spk':'1'}]
    pipeline.guard_cache(tmp_path)
    pipeline.guard_cache(tmp_path,us)
    pipeline.guard_cache(tmp_path,us)
    with pytest.raises(ValueError,match='Incompatible'):
        pipeline.guard_cache(tmp_path,[{**us[0],'spk':'2'}])
    with monkeypatch.context() as m:
        m.setattr(pipeline.config,'VOICE_ID','different_voice')
        with pytest.raises(ValueError,match='Incompatible'): pipeline.guard_cache(tmp_path)
    clip(tmp_path/'source.wav', .2)
    with pytest.raises(ValueError,match='Incompatible'): pipeline.guard_cache(tmp_path)


def test_no_tail_mix_keeps_exact_source_duration(tmp_path):
    r = mix.place([{'start':0}], [clip(tmp_path/'a.wav',.5)], 2, tmp_path/'out.wav')
    assert voice.duration(tmp_path/'out.wav') == 2
    assert r['tail_overflow'] == 0


def test_no_tail_mux_keeps_source_duration(tmp_path):
    import subprocess
    source = tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=black:s=160x90:r=30:d=2',
                    '-c:v','libx264',str(source)],check=True)
    wav = tmp_path/'out.wav'
    mix.place([{'start':0}], [clip(tmp_path/'a.wav',.5)], 2, wav)
    m4a = tmp_path/'dub.m4a'
    mix.mix(wav,None,m4a)
    target=tmp_path/'dub.mp4'
    pipeline._ff('-i',str(source),'-i',str(m4a),'-map','0:v','-map','1:a','-c','copy',str(target))
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
                                          '-of','csv=p=0',str(target)]))
    assert duration == pytest.approx(2,abs=.025)


def test_same_speaker_overlong_clip_misses_anchor_without_self_overlap(tmp_path):
    us=[{'start':0,'end':1,'spk':'a'}, {'start':1,'end':2,'spk':'a','hard_anchor':True}]
    result=mix.place(us,[clip(tmp_path/'a.wav',1.5),clip(tmp_path/'b.wav',.4)],2,tmp_path/'out.wav')
    assert result['starts'][1] == 1.58
    assert result['overlap_lines'] == 0 and result['anchor_violation_lines'] == 1
    assert result['late_max'] == .58


def test_distinct_speaker_overlap_uses_headroom_not_hard_clipping(tmp_path):
    import array
    us=[{'start':0,'spk':'a'}, {'start':.5,'spk':'b'}]
    result=mix.place(us,[clip(tmp_path/'a.wav',1,20000),clip(tmp_path/'b.wav',1,20000)],2,tmp_path/'out.wav')
    x=array.array('h',voice.pcm(tmp_path/'out.wav'))
    assert result['overlap_headroom_gain_db'] < 0
    assert abs(x[int(.75*voice.RATE)] / x[int(.25*voice.RATE)] - 2) < .001
    assert max(x) <= 32767


def test_publication_failure_does_not_drop_synthesized_language(monkeypatch,tmp_path):
    monkeypatch.setattr(pipeline,'dub_language',lambda *a: {'lang':a[3]})
    def publish(*a): raise RuntimeError('temporary storage failure')
    reports, failures=pipeline._languages(tmp_path,[],'ko',['en'],{},1,None,publish)
    assert reports == [{'lang':'en','publication_warning':'RuntimeError'}]
    assert failures == []


def test_regeneration_preserves_legacy_background_filename(monkeypatch,tmp_path):
    cached_run(tmp_path)
    legacy=clip(tmp_path/'no_vocals.wav',2)
    monkeypatch.setattr(pipeline.agent,'repair_line',lambda u,text,*a,**k:
                        {'id':u['id'],'text':text,'dur':.4,'slot':1,'tempo':1,'ok':True,'actions':[{'do':'check','ok':True}]})
    seen=[]
    monkeypatch.setattr(pipeline.mix,'mix',lambda src,bed,out: seen.append(bed))
    pipeline.regenerate_line(tmp_path,'en',1,'Edited')
    assert seen == [legacy]


@pytest.mark.parametrize('generation_sec', [10.0, None])
def test_repeated_remix_preserves_generation_timing_and_provenance(monkeypatch, tmp_path, generation_sec):
    us=cached_run(tmp_path)
    path=tmp_path/'dub/en.json'
    data=json.loads(path.read_text())
    data['report'].update(sec=generation_sec, timing_provenance={'source':'original generation or unknown'})
    path.write_text(json.dumps(data))
    monkeypatch.setattr(pipeline.agent,'repair_line',no_paid)
    monkeypatch.setattr(pipeline.mix,'mix',lambda *a: None)
    first=pipeline.dub_language(tmp_path,us,'ko','en',{},2,None,offline=True)
    second=pipeline.dub_language(tmp_path,us,'ko','en',{},2,None,offline=True)
    assert first['sec'] == second['sec'] == generation_sec
    assert first['timing_provenance'] == second['timing_provenance'] == data['report']['timing_provenance']
    assert first['remix_sec'] >= 0 and second['remix_sec'] >= 0
