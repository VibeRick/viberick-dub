import copy
import json
from pathlib import Path

import pytest
from google.api_core.exceptions import AlreadyExists

from tools import publish_review_sample as publisher


@pytest.fixture
def sample(tmp_path):
    run = tmp_path / "run"
    (run / "out").mkdir(parents=True)
    (run / "dub").mkdir()
    units = [{"id": 0, "start": 0, "end": 2, "text": "Hello", "spk": "a", "voice": "Charon"}]
    (run / "units.json").write_text(json.dumps(units))
    report = {"video": "abc12345678", "src": "en", "duration": 2, "langs": [{"lang": "ko"}], "units": 1}
    (run / "dub/ko.json").write_text(json.dumps({"report": {"lang": "ko"}, "rows": [
        {"id": 0, "text": "안녕", "start": 0, "end": 1.5, "dur": 1.5}]}))
    (run / "events.jsonl").write_text('{"t":1,"kind":"start"}\n')
    names = {"report.json", "video.orig.mp4", "subs.en.srt", "subs.en.vtt", "video.ko.mp4", "dub.ko.m4a",
             "subs.ko.srt", "subs.ko.vtt", "timeline.ko.json"}
    for name in names:
        (run / "out" / name).write_text("{}" if name.endswith(".json") else "fixture")
    (run / "out/report.json").write_text(json.dumps(report))
    manifest = {"job": {"title": "Reviewed podcast", "src": "en", "url": "https://youtu.be/abc12345678?t=10",
                           "source_interval": {"start": 10, "end": 12}, "voice_disclosure": "AI preset voices, not clones",
                           "alignment_provenance": "Prepared source turns", "validation_scope": "prepared_source_turns",
                           "source_captioned": False, "speakers": {"a": {"name": "Speaker", "voice_type": "preset", "voice": "Charon"}},
                           "langs": ["ko"], "report": report, "outputs": {name: name for name in names}},
                "lines": {"ko": publisher.cloud.result_document(run, "ko")}, "events": [{"t": 1, "kind": "start"}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return run, path


def test_plan_is_offline_deterministic_and_content_addressed(sample, monkeypatch):
    monkeypatch.setattr(publisher.cloud, "db", lambda: pytest.fail("dry run connected to cloud"))
    a = publisher.build_plan(*sample)
    assert a == publisher.build_plan(*sample)
    assert "/tmp/" not in json.dumps(a["plan"])
    (sample[0] / "out/video.ko.mp4").write_text("changed media")
    b = publisher.build_plan(*sample)
    assert a["job_id"] != b["job_id"] and a["fingerprint"] != b["fingerprint"]


def test_plan_rejects_manifest_drift_extra_files_and_private_paths(sample):
    run, manifest_path = sample
    extra = run / "out/private.wav"
    extra.write_text("not reviewed")
    with pytest.raises(ValueError, match="directory differs"):
        publisher.build_plan(*sample)
    extra.unlink()
    manifest = json.loads(manifest_path.read_text())
    manifest["job"]["alignment_provenance"] = "/Users/person/private/source.json"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="absolute path"):
        publisher.build_plan(*sample)


class Store:
    def __init__(self): self.docs = {}
    def ref(self, name): return Ref(self, name)
    def transaction(self): return self
    def update(self, ref, data): ref.update(data)


class Ref:
    def __init__(self, store, name): self.store, self.name = store, name
    def get(self, **kwargs): return self
    def to_dict(self): return copy.deepcopy(self.store.docs.get(self.name))
    def create(self, data):
        if self.name in self.store.docs: raise AlreadyExists("exists")
        self.store.docs[self.name] = copy.deepcopy(data)
    def update(self, data): self.store.docs[self.name].update(copy.deepcopy(data))
    def collection(self, name): return Collection(self.store, self.name + "/" + name)


class Collection:
    def __init__(self, store, name): self.store, self.name = store, name
    def document(self, name): return Ref(self.store, self.name + "/" + name)


@pytest.fixture
def publication(monkeypatch):
    store = Store()
    monkeypatch.setattr(publisher.cloud, "job", store.ref)
    monkeypatch.setattr(publisher.cloud, "db", lambda: store)
    monkeypatch.setattr(publisher.firestore, "transactional", lambda function: function)
    monkeypatch.setattr(publisher.cloud, "publish_results", lambda *args: None)
    return store


def test_publication_visibility_last_and_same_fingerprint_is_noop(sample, publication, monkeypatch):
    plan = publisher.build_plan(*sample)
    calls = []
    def upload(run, job_id, demo):
        current = publication.docs[job_id]
        assert current["demo"] is False and current["featured"] is False and current["can_regenerate"] is False
        calls.append(job_id)
        return {file["name"]: "https://example/" + file["name"] for file in plan["payload"]["files"]}
    monkeypatch.setattr(publisher.cloud, "upload_outputs", upload)
    assert publisher.publish(plan, sample[0])["status"] == "published"
    current = publication.docs[plan["job_id"]]
    assert current["demo"] is True and current["featured"] is True and current["can_regenerate"] is False
    assert current["source_interval"] == {"start": 10, "end": 12}
    assert len([key for key in publication.docs if "/events/" in key]) == 1
    assert publisher.publish(plan, sample[0])["status"] == "already_published"
    assert len(calls) == 1


def test_existing_unrelated_job_cannot_be_overwritten(sample, publication, monkeypatch):
    plan = publisher.build_plan(*sample)
    publication.docs[plan["job_id"]] = {"title": "Someone else's job"}
    monkeypatch.setattr(publisher.cloud, "upload_outputs", lambda *a, **k: pytest.fail("uploaded on collision"))
    with pytest.raises(ValueError, match="refusing overwrite"):
        publisher.publish(plan, sample[0])
    assert publication.docs[plan["job_id"]] == {"title": "Someone else's job"}


def test_failed_upload_stays_unlisted_and_resume_preserves_stable_events(sample, publication, monkeypatch):
    plan = publisher.build_plan(*sample)
    def failed(*args, **kwargs): raise OSError("network interrupted")
    monkeypatch.setattr(publisher.cloud, "upload_outputs", failed)
    with pytest.raises(OSError): publisher.publish(plan, sample[0])
    assert publication.docs[plan["job_id"]]["demo"] is False
    events = {key: value for key, value in publication.docs.items() if "/events/" in key}
    monkeypatch.setattr(publisher.cloud, "upload_outputs", lambda *a, **k: {f["name"]: "url" for f in plan["payload"]["files"]})
    publisher.publish(plan, sample[0])
    assert events == {key: value for key, value in publication.docs.items() if "/events/" in key}
