from dub import cloud


def test_non_demo_outputs_go_under_the_expiring_prefix():
    assert cloud.output_prefix("abc", demo=False) == "jobs/abc"
    assert cloud.output_prefix("abc", demo=True) == "demo/abc"


def test_result_rows_preserve_dub_timing_and_match_by_id(tmp_path):
    import json
    (tmp_path / "dub").mkdir()
    (tmp_path / "units.json").write_text(json.dumps([
        {"id": 1, "start": 1, "end": 2, "text": "one"},
        {"id": 2, "start": 4, "end": 6, "text": "two"}]))
    (tmp_path / "dub/en.json").write_text(json.dumps({"report": {}, "rows": [
        {"id": 2, "start": 3.5, "end": 5.2, "text": "two translated"},
        {"id": 1, "dub_start": 1.1, "dub_end": 2.4, "text": "one translated"}]}))
    rows = cloud.result_document(tmp_path, "en")["rows"]
    assert rows[0]["start"] == 3.5 and rows[0]["source_start"] == 4 and rows[0]["src"] == "two"
    assert rows[1]["end"] == 2.4 and rows[1]["source_end"] == 2


def test_workspace_roundtrip_is_private_and_contains_report(monkeypatch, tmp_path):
    blobs = {}
    buckets = []

    class Blob:
        def __init__(self, name): self.name = name
        def upload_from_filename(self, path, **kw): blobs[self.name] = path.read_bytes()
        def download_to_filename(self, path): path.write_bytes(blobs[self.name])
    class Bucket:
        def blob(self, name): return Blob(name)
    class Client:
        def bucket(self, name): buckets.append(name); return Bucket()
    monkeypatch.setattr(cloud.storage, "Client", lambda **kw: Client())
    monkeypatch.setattr(cloud.config, "gcp_credentials", lambda: None)
    source = tmp_path / "source"
    (source / "out").mkdir(parents=True)
    (source / "out/report.json").write_text('{"src":"ko"}')
    (source / "out/video.orig.mp4").write_bytes(b"not needed duplicate")
    (source / "source.mp4").write_bytes(b"private source")
    name = cloud.save_workspace(source, "job")
    destination = tmp_path / "restored"
    cloud.load_workspace(name, destination)
    assert (destination / "out/report.json").exists()
    assert (destination / "source.mp4").read_bytes() == b"private source"
    assert not (destination / "out/video.orig.mp4").exists()
    assert set(buckets) == {cloud.config.BUCKET}
    assert cloud.PUBLIC_BUCKET not in buckets


def test_incremental_upload_includes_source_comparison_but_not_other_languages(monkeypatch, tmp_path):
    uploaded = []
    class Blob:
        def __init__(self, name): self.name = name
        def upload_from_filename(self, path, **kwargs): uploaded.append(path.name)
    class Bucket:
        def blob(self, name): return Blob(name)
    class Client:
        def bucket(self, name): return Bucket()
    monkeypatch.setattr(cloud.storage, "Client", lambda **kwargs: Client())
    monkeypatch.setattr(cloud.config, "gcp_credentials", lambda: None)
    (tmp_path / "out").mkdir()
    names = {"video.orig.mp4", "subs.ko.srt", "subs.ko.vtt", "dub.en.m4a", "video.en.mp4", "subs.en.vtt",
             "timeline.en.json", "line.en.1.attempt0.wav", "dub.ja.m4a", "subs.ja.vtt"}
    for name in names: (tmp_path / "out" / name).write_bytes(b"fixture")
    urls = cloud.upload_outputs(tmp_path, "job", lang="en", include_source="ko")
    assert {"video.orig.mp4", "subs.ko.srt", "subs.ko.vtt", "dub.en.m4a", "subs.en.vtt"} <= urls.keys()
    assert "dub.ja.m4a" not in urls and "subs.ja.vtt" not in urls
    uploaded.clear()
    cloud.upload_outputs(tmp_path, "job", lang="ja")
    assert set(uploaded) == {"dub.ja.m4a", "subs.ja.vtt"}
    uploaded.clear()
    cloud.upload_outputs(tmp_path, "job", skip_names=set(urls))
    assert "video.orig.mp4" not in uploaded and "subs.ko.vtt" not in uploaded
