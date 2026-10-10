from fastapi.testclient import TestClient

import server.app as app_mod


class FakeDoc:
    store: dict = {}

    def __init__(self, i): self.i = i
    def set(self, d): FakeDoc.store[self.i] = d
    def update(self, d): FakeDoc.store[self.i].update(d)


class FakeQuery:
    def where(self, *a, **k): return self
    def limit(self, n): return self
    def stream(self): return []


class FakeDB:
    def collection(self, name): return FakeQuery()


def client(monkeypatch):
    FakeDoc.store = {}
    monkeypatch.setattr(app_mod.cloud, "db", lambda: FakeDB())
    monkeypatch.setattr(app_mod.cloud, "job", lambda i: FakeDoc(i))
    started = []

    class Jobs:
        def run_job(self, req): started.append(req)
    monkeypatch.setattr(app_mod.run_v2, "JobsClient", lambda: Jobs())
    return TestClient(app_mod.app), started


def test_duplicate_langs_are_collapsed(monkeypatch):
    c, started = client(monkeypatch)
    r = c.post("/api/jobs", json={"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"] * 500})
    assert r.status_code == 200 and list(FakeDoc.store.values())[0]["langs"] == ["en"] and len(started) == 1


def test_channel_or_playlist_url_is_rejected_without_running_ytdlp(monkeypatch):
    c, started = client(monkeypatch)
    monkeypatch.setattr(app_mod.fetch.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("yt-dlp ran")))
    for url in ("https://www.youtube.com/@bigchannel", "https://www.youtube.com/playlist?list=PL123"):
        assert c.post("/api/jobs", json={"url": url, "langs": ["en"]}).status_code == 400
    assert started == []
