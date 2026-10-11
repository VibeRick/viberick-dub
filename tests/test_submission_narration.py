import json
from pathlib import Path
import pytest
from tools import attach_submission_narration as narration


def fixture(tmp_path):
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'take.wav').write_bytes(b'local test fixture')
    script = tmp_path / 'script.json'
    script.write_text(json.dumps({'intro': {'text':'Exact words.', 'frames':90, 'audio':None}}))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'intro': {'text':'Exact words.', 'file':'take.wav'}}))
    return script, manifest, public


def test_attaches_actual_duration_with_complete_tail(tmp_path, monkeypatch):
    script, manifest, public = fixture(tmp_path)
    monkeypatch.setattr(narration, 'probe_seconds', lambda _: 3.2)
    result = narration.attach(script, manifest, public)
    row = json.loads(script.read_text())['intro']
    assert row['frames'] == 108
    assert row['audio'] == 'take.wav'
    assert len(row['audioSha256']) == 64
    assert result['frames'] == narration.PROOF_FRAMES + 108


@pytest.mark.parametrize('change', ['text', 'escape', 'overlong', 'missing'])
def test_rejects_invalid_take_without_changing_script(tmp_path, monkeypatch, change):
    script, manifest, public = fixture(tmp_path)
    before = script.read_bytes()
    take = json.loads(manifest.read_text())
    if change == 'text': take['intro']['text'] = 'Old wording.'
    if change == 'escape': take['intro']['file'] = '../take.wav'
    if change == 'missing': take = {}
    manifest.write_text(json.dumps(take))
    monkeypatch.setattr(narration, 'probe_seconds', lambda _: 179 if change == 'overlong' else 3.2)
    with pytest.raises(ValueError): narration.attach(script, manifest, public)
    assert script.read_bytes() == before
