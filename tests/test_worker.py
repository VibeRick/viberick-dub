import pytest
from dub import worker


@pytest.fixture(autouse=True)
def fake_transactions(monkeypatch):
    from tests.test_server import FakeDB
    monkeypatch.setattr(worker.cloud, "db", lambda: FakeDB())
    monkeypatch.setattr(worker.firestore, "transactional", lambda f: f)


def test_sigterm_marks_the_job_failed():
    updates = []

    class Ref:
        def update(self, d): updates.append(d)
    handler = worker.on_terminate(Ref())
    try:
        handler(15, None)
    except SystemExit:
        pass
    assert updates and updates[0]["status"] == "error"


def test_heartbeat_runs_independently_and_survives_transient_write_failure():
    updates = []
    class Stop:
        count = 0
        def wait(self, seconds):
            self.count += 1
            return self.count > 2
    class Ref:
        def update(self, value):
            updates.append(value)
            if len(updates) == 1:
                raise RuntimeError("temporary outage")
    worker.heartbeat(Ref(), Stop())
    assert len(updates) == 2 and "heartbeat" in updates[-1]


def test_partial_language_is_published_before_pipeline_completes(monkeypatch, tmp_path):
    import json
    state = {"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en", "ja"], "max_sec": 10}
    updates = []
    class Ref:
        def get(self, **kwargs): return self
        def to_dict(self): return state
        def update(self, data): updates.append(dict(data)); state.update(data)
    monkeypatch.setattr(worker.cloud, "job", lambda _: Ref())
    monkeypatch.setattr(worker.cloud, "access", lambda _: Ref())
    monkeypatch.setattr(worker.cloud, "event_sink", lambda _: lambda *args: None)
    monkeypatch.setattr(worker.cloud, "upload_outputs", lambda *args, **kw: {"dub.en.m4a": "url"})
    monkeypatch.setattr(worker.cloud, "publish_results", lambda *args, **kw: None)
    monkeypatch.setattr(worker.cloud, "save_workspace", lambda *args: "private/workspace")
    (tmp_path / "out").mkdir()
    report = {"langs": [{"lang": "en"}], "failures": [{"lang": "ja", "error": "RuntimeError"}]}
    (tmp_path / "out/report.json").write_text(json.dumps(report))
    def pipeline(*args, on_language_done):
        on_language_done(tmp_path, "en", {"lang": "en"})
        assert state["outputs"]["dub.en.m4a"] == "url"
        assert state["status"] == "running"
        return tmp_path
    monkeypatch.setattr(worker.pipeline, "main", pipeline)
    monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
    worker.run("job")
    assert state["status"] == "partial" and state["can_regenerate"]
    assert worker.events._sinks == []


def test_worker_error_never_exposes_exception_to_public_document(monkeypatch):
    import pytest
    state = {"url": "url"}
    class Ref:
        def get(self, **kwargs): return self
        def to_dict(self): return state
        def update(self, data): state.update(data)
    monkeypatch.setattr(worker.cloud, "job", lambda _: Ref())
    monkeypatch.setattr(worker.cloud, "event_sink", lambda _: lambda *args: None)
    monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
    def fail(*args, **kwargs): raise RuntimeError("private credential detail")
    monkeypatch.setattr(worker.pipeline, "main", fail)
    with pytest.raises(RuntimeError): worker.run("job")
    assert state["status"] == "error"
    assert "private credential detail" not in state["error"]
    assert worker.events._sinks == []


def test_preview_only_publishes_staged_outputs_until_accept(monkeypatch, tmp_path):
    from tests.test_server import FakeDoc
    FakeDoc.store = {
        "job": {"outputs": {"dub.en.m4a": "original"}},
        "access/job": {"active_edit": "edit", "workspace": "private/initial"},
        "job/edits/edit": {"status": "queued", "lang": "en", "line_id": 1, "text": "Edited", "revision": 0}}
    monkeypatch.setattr(worker.cloud, "job", lambda _: FakeDoc("job"))
    monkeypatch.setattr(worker.cloud, "access", lambda _: FakeDoc("access/job"))
    loaded = []
    monkeypatch.setattr(worker.cloud, "load_workspace", lambda name, dest: loaded.append((name, dest)))
    monkeypatch.setattr(worker.pipeline, "regenerate_line", lambda *args: {"lang": "en", "ok": 1})
    monkeypatch.setattr(worker.cloud, "upload_outputs", lambda *args, **kw: {"dub.en.m4a": "preview"})
    monkeypatch.setattr(worker.cloud, "save_workspace", lambda *args: "private/edit")
    monkeypatch.setattr(worker.cloud, "result_document", lambda *args: {"rows": [{"id": 1, "text": "Edited", "start": 2}]})
    worker.preview("job", "edit")
    assert loaded and loaded[0][0] == "private/initial"
    assert FakeDoc.store["job"]["outputs"]["dub.en.m4a"] == "original"
    assert FakeDoc.store["job/edits/edit"]["status"] == "ready"
    assert FakeDoc.store["job/edits/edit"]["outputs"]["dub.en.m4a"] == "preview"
    assert FakeDoc.store["access/job/edits/edit"]["workspace"] == "private/edit"
    worker.preview("job", "edit")
    assert len(loaded) == 1  # delivery retry never repeats synthesis


def test_claim_is_single_attempt_and_expired_lease_cannot_publish():
    from tests.test_server import FakeDoc
    import time
    FakeDoc.store = {"job": {"status": "queued"}}
    ref = FakeDoc("job")
    token = worker.claim(ref)
    assert token and worker.claim(ref) is None
    ref.update({"lease_until": time.time() - 1})
    assert not worker.fenced_update(ref, token, {"status": "ready"})
    assert ref.to_dict()["status"] == "running"


def test_first_language_exposes_original_and_source_captions_before_second_finishes(monkeypatch, tmp_path):
    import json
    from tests.test_server import FakeDoc
    FakeDoc.store = {"job": {"status": "queued", "url": "url", "langs": ["en", "ja"]}, "access/job": {}}
    monkeypatch.setattr(worker.cloud, "job", lambda _: FakeDoc("job"))
    monkeypatch.setattr(worker.cloud, "access", lambda _: FakeDoc("access/job"))
    monkeypatch.setattr(worker.cloud, "event_sink", lambda _: lambda *args: None)
    monkeypatch.setattr(worker.cloud, "publish_results", lambda *args, **kw: None)
    monkeypatch.setattr(worker.cloud, "save_workspace", lambda *args: "private/workspace")
    monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
    uploaded = []
    def upload(*args, lang=None, include_source=None, skip_names=None, **kwargs):
        uploaded.append({"lang": lang, "include_source": include_source, "skip_names": skip_names})
        result = {f"dub.{lang}.m4a": "dub", f"subs.{lang}.vtt": "caption"} if lang else {"report.json": "report"}
        if include_source:
            result.update({"video.orig.mp4": "original", f"subs.{include_source}.vtt": "original caption"})
        return result
    monkeypatch.setattr(worker.cloud, "upload_outputs", upload)
    (tmp_path / "out").mkdir()
    summary = {"src": "ko", "langs": [{"lang": "en", "src": "ko"}, {"lang": "ja", "src": "ko"}]}
    (tmp_path / "out/report.json").write_text(json.dumps(summary))
    def pipeline(*args, on_language_done):
        on_language_done(tmp_path, "en", summary["langs"][0])
        current = FakeDoc.store["job"]
        assert current["status"] == "running" and current["src"] == "ko"
        assert {"video.orig.mp4", "subs.ko.vtt", "dub.en.m4a", "subs.en.vtt"} <= current["outputs"].keys()
        on_language_done(tmp_path, "ja", summary["langs"][1])
        return tmp_path
    monkeypatch.setattr(worker.pipeline, "main", pipeline)
    worker.run("job")
    assert [call["include_source"] for call in uploaded] == ["ko", None, None]
    assert "video.orig.mp4" in uploaded[-1]["skip_names"]
    assert FakeDoc.store["job"]["src"] == "ko"
