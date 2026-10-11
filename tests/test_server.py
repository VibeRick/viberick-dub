from fastapi.testclient import TestClient

import server.app as app_mod


class FakeDoc:
    store: dict = {}

    def __init__(self, i): self.i = i
    def set(self, d): FakeDoc.store[self.i] = d
    def update(self, d): FakeDoc.store[self.i].update(d)
    def get(self, **kwargs): return self
    def to_dict(self): return FakeDoc.store.get(self.i)
    def collection(self, name): return FakeCollection(f"{self.i}/{name}")


class FakeCollection:
    def __init__(self, path): self.path = path
    def document(self, i): return FakeDoc(f"{self.path}/{i}")


class FakeTransaction:
    def set(self, ref, data): ref.set(data)
    def update(self, ref, data): ref.update(data)


class FakeQuery:
    def where(self, *a, **k): return self
    def limit(self, n): return self
    def stream(self): return []


class FakeDB:
    def collection(self, name): return FakeCollection(name)
    def transaction(self): return FakeTransaction()


def client(monkeypatch):
    FakeDoc.store = {}
    monkeypatch.setattr(app_mod.cloud, "db", lambda: FakeDB())
    monkeypatch.setattr(app_mod.cloud, "job", lambda i: FakeDoc(i))
    monkeypatch.setattr(app_mod.cloud, "access", lambda i: FakeDoc(f"access/{i}"))
    monkeypatch.setattr(app_mod.firestore, "transactional", lambda f: f)
    started = []

    class Jobs:
        def run_job(self, req): started.append(req)
    monkeypatch.setattr(app_mod.run_v2, "JobsClient", lambda: Jobs())
    return TestClient(app_mod.app), started


def test_duplicate_langs_are_collapsed(monkeypatch):
    c, started = client(monkeypatch)
    r = c.post("/api/jobs", json={"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"] * 500})
    assert r.status_code == 200 and FakeDoc.store[r.json()["id"]]["langs"] == ["en"] and len(started) == 1


def test_worker_receives_only_canonical_video_url(monkeypatch):
    c, started = client(monkeypatch)
    response = c.post("/api/jobs", json={"url": "https://www.youtube.com/redirect?v=Fty2sz3dBwU&next=https://example.org"})
    assert response.status_code == 200 and len(started) == 1
    assert FakeDoc.store[response.json()["id"]]["url"] == "https://www.youtube.com/watch?v=Fty2sz3dBwU"


def test_channel_or_playlist_url_is_rejected_without_running_ytdlp(monkeypatch):
    c, started = client(monkeypatch)
    monkeypatch.setattr(app_mod.fetch.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("yt-dlp ran")))
    for url in ("https://www.youtube.com/@bigchannel", "https://www.youtube.com/playlist?list=PL123"):
        assert c.post("/api/jobs", json={"url": url, "langs": ["en"]}).status_code == 400
    assert started == []


def test_duration_requires_finite_positive_number(monkeypatch):
    c, started = client(monkeypatch)
    for duration in (0, -1, "NaN", "Infinity", "-Infinity"):
        response = c.post("/api/jobs", json={"url": "https://youtu.be/Fty2sz3dBwU", "max_sec": duration})
        assert response.status_code == 422
    assert not started


def editable_job(c):
    response = c.post("/api/jobs", json={"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"]}).json()
    job_id = response["id"]
    FakeDoc(job_id).update({"status": "done", "can_regenerate": True, "outputs": {"old": "url"},
                            "report": {"langs": [{"lang": "en", "ok": 0}]}})
    FakeDoc(f"{job_id}/lines/en").set({"rows": [{"id": 1}]})
    FakeDoc(f"access/{job_id}").update({"workspace": "workspaces/initial.tar.gz"})
    return job_id, response["owner_token"]


def test_owner_hash_is_private_and_token_returned_once(monkeypatch):
    c, _ = client(monkeypatch)
    job_id, token = editable_job(c)
    assert token and "token_hash" not in FakeDoc.store[job_id]
    assert token not in str(FakeDoc.store)
    assert len(FakeDoc.store[f"access/{job_id}"]["token_hash"]) == 64


def test_regeneration_requires_owner_and_current_revision(monkeypatch):
    c, started = client(monkeypatch)
    job_id, token = editable_job(c)
    path = f"/api/jobs/{job_id}/lines/en/1/regenerate"
    assert c.post(path, json={"text": "Hello", "revision": 0}).status_code == 403
    headers = {"X-Job-Token": token}
    assert c.post(path, json={"text": "Hello", "revision": 5}, headers=headers).status_code == 409
    result = c.post(path, json={"text": "Hello", "revision": 0}, headers=headers)
    assert result.status_code == 200
    assert len(started) == 2
    assert FakeDoc.store[f"{job_id}/edits/{result.json()['edit_id']}"]["status"] == "queued"
    assert c.post(path, json={"text": "Again", "revision": 0}, headers=headers).status_code == 409


def test_preview_accept_requires_ready_and_preserves_other_outputs(monkeypatch):
    c, _ = client(monkeypatch)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    edit_id = c.post(f"/api/jobs/{job_id}/lines/en/1/regenerate",
                     json={"text": "Hello", "revision": 0}, headers=headers).json()["edit_id"]
    path = f"/api/jobs/{job_id}/edits/{edit_id}/accept"
    assert c.post(path, json={"revision": 0}, headers=headers).status_code == 409
    FakeDoc(f"{job_id}/edits/{edit_id}").update({"status": "ready", "outputs": {"dub.en.m4a": "new"},
                                                "report": {"lang": "en", "ok": 1}})
    FakeDoc(f"access/{job_id}/edits/{edit_id}").set({"workspace": "new/private", "result": {"rows": [{"id": 1, "text": "Hello"}]}})
    assert c.post(path, json={"revision": 0}, headers=headers).json()["revision"] == 1
    assert FakeDoc.store[job_id]["outputs"] == {"old": "url", "dub.en.m4a": "new"}
    assert FakeDoc.store[f"access/{job_id}"]["workspace"] == "new/private"
    assert c.post(path, json={"revision": 0}, headers=headers).status_code == 409


def test_discard_unlocks_finished_failed_preview(monkeypatch):
    c, _ = client(monkeypatch)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    edit_id = c.post(f"/api/jobs/{job_id}/lines/en/1/regenerate",
                     json={"text": "Hello", "revision": 0}, headers=headers).json()["edit_id"]
    path = f"/api/jobs/{job_id}/edits/{edit_id}/discard"
    assert c.post(path, json={"revision": 0}, headers=headers).status_code == 409
    FakeDoc(f"{job_id}/edits/{edit_id}").update({"status": "error"})
    assert c.post(path, json={"revision": 0}, headers=headers).status_code == 200
    assert FakeDoc.store[f"access/{job_id}"]["active_edit"] is None


def operation_count():
    return sum(value.get("operations", 0) for key, value in FakeDoc.store.items() if key.startswith("quotas/operations-"))


def test_daily_operations_cap_covers_creation_and_regeneration(monkeypatch):
    c, started = client(monkeypatch)
    monkeypatch.setattr(app_mod, "DAILY_CAP", 2)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    path = f"/api/jobs/{job_id}/lines/en/1/regenerate"
    assert c.post(path, json={"text": "Hi", "revision": 10}, headers=headers).status_code == 409
    assert operation_count() == 1
    result = c.post(path, json={"text": "Hi", "revision": 0}, headers=headers)
    assert result.status_code == 200 and operation_count() == 2
    assert c.post(path, json={"text": "Hi", "revision": 0}, headers=headers).status_code == 409
    assert operation_count() == 2
    assert c.post("/api/jobs", json={"url": "https://youtu.be/Fty2sz3dBwU"}).status_code == 429
    assert len(started) == 2


def test_job_edit_cap_survives_discard(monkeypatch):
    c, started = client(monkeypatch)
    monkeypatch.setattr(app_mod, "EDIT_CAP", 1)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    path = f"/api/jobs/{job_id}/lines/en/1/regenerate"
    edit_id = c.post(path, json={"text": "Hi", "revision": 0}, headers=headers).json()["edit_id"]
    FakeDoc(f"{job_id}/edits/{edit_id}").update({"status": "error"})
    c.post(f"/api/jobs/{job_id}/edits/{edit_id}/discard", json={"revision": 0}, headers=headers)
    assert c.post(path, json={"text": "Again", "revision": 0}, headers=headers).status_code == 429
    assert operation_count() == 2 and len(started) == 2


def test_create_idempotency_replay_does_not_launch_or_spend_again(monkeypatch):
    c, started = client(monkeypatch)
    headers = {"Idempotency-Key": "unique-client-attempt"}
    body = {"url": "https://youtu.be/Fty2sz3dBwU"}
    assert c.post("/api/jobs", json=body, headers=headers).status_code == 200
    assert c.post("/api/jobs", json=body, headers=headers).status_code == 403
    assert operation_count() == 1 and len(started) == 1


def test_expired_preview_can_be_discarded_and_late_worker_is_fenced(monkeypatch):
    from dub import worker
    c, _ = client(monkeypatch)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    path = f"/api/jobs/{job_id}/lines/en/1/regenerate"
    edit_id = c.post(path, json={"text": "Hi", "revision": 0}, headers=headers).json()["edit_id"]
    ref = FakeDoc(f"{job_id}/edits/{edit_id}")
    ref.update({"status": "running", "lease_until": app_mod.time.time() - 1, "lease_token": "dead-worker"})
    assert c.post(f"/api/jobs/{job_id}/edits/{edit_id}/discard", json={"revision": 0}, headers=headers).status_code == 200
    assert not worker.fenced_update(ref, "dead-worker", {"status": "ready"})
    assert ref.to_dict()["status"] == "discarded"


def test_reconcile_only_expires_stale_lease(monkeypatch):
    c, _ = client(monkeypatch)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    ref = FakeDoc(job_id)
    ref.update({"status": "running", "lease_until": app_mod.time.time() + 100, "lease_token": "worker"})
    path = f"/api/jobs/{job_id}/reconcile"
    assert c.post(path, headers=headers).json() == {"recovered": False}
    ref.update({"lease_until": app_mod.time.time() - 1})
    assert c.post(path, headers=headers).json() == {"recovered": True}
    assert ref.to_dict()["status"] == "error" and ref.to_dict()["lease_token"] is None


def test_launch_failure_remains_discardable_before_retry(monkeypatch):
    c, started = client(monkeypatch)
    job_id, token = editable_job(c)
    headers = {"X-Job-Token": token}
    path = f"/api/jobs/{job_id}/lines/en/1/regenerate"
    launch = app_mod.launch
    def fail(*args, **kwargs): raise RuntimeError("worker unavailable")
    monkeypatch.setattr(app_mod, "launch", fail)
    assert c.post(path, json={"text": "Hi", "revision": 0}, headers=headers).status_code == 503
    access = FakeDoc(f"access/{job_id}").to_dict()
    edit_id = access["active_edit"]
    assert FakeDoc(f"{job_id}/edits/{edit_id}").to_dict()["status"] == "error"
    assert operation_count() == 2 and access["edit_count"] == 1
    assert c.post(f"/api/jobs/{job_id}/edits/{edit_id}/discard", json={"revision": 0}, headers=headers).status_code == 200
    monkeypatch.setattr(app_mod, "launch", launch)
    assert c.post(path, json={"text": "Hi again", "revision": 0}, headers=headers).status_code == 200
    assert operation_count() == 3 and access["edit_count"] == 2



def test_lost_create_response_recovery_returns_same_job_even_when_quota_full(monkeypatch):
    import secrets
    c, started = client(monkeypatch)
    monkeypatch.setattr(app_mod, "DAILY_CAP", 1)
    token = secrets.token_urlsafe(32)
    headers = {"Idempotency-Key": "lost-response", "X-Job-Token": token}
    body = {"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"]}
    first = c.post("/api/jobs", json=body, headers=headers).json()
    # Pretend the caller never received the first response, then retry using persisted headers.
    recovered = c.post("/api/jobs", json=body, headers=headers)
    assert recovered.status_code == 200
    assert recovered.json() == {"id": first["id"], "owner_token": token, "revision": 0, "replayed": True}
    assert operation_count() == 1 and len(started) == 1
    assert token not in str(FakeDoc.store)


def test_recovery_cannot_guess_request_key_or_change_payload(monkeypatch):
    import secrets
    c, started = client(monkeypatch)
    headers = {"Idempotency-Key": "known-key", "X-Job-Token": secrets.token_urlsafe(32)}
    body = {"url": "https://youtu.be/Fty2sz3dBwU", "langs": ["en"]}
    assert c.post("/api/jobs", json=body, headers=headers).status_code == 200
    guessed = {**headers, "X-Job-Token": secrets.token_urlsafe(32)}
    assert c.post("/api/jobs", json=body, headers=guessed).status_code == 403
    assert c.post("/api/jobs", json={**body, "langs": ["ja"]}, headers=headers).status_code == 409
    assert operation_count() == 1 and len(started) == 1


def test_known_server_generated_owner_token_can_recover_request(monkeypatch):
    c, started = client(monkeypatch)
    headers = {"Idempotency-Key": "server-generated-token"}
    body = {"url": "https://youtu.be/Fty2sz3dBwU"}
    first = c.post("/api/jobs", json=body, headers=headers).json()
    recovered = c.post("/api/jobs", json=body, headers={**headers, "X-Job-Token": first["owner_token"]})
    assert recovered.status_code == 200 and recovered.json()["id"] == first["id"]
    assert operation_count() == 1 and len(started) == 1
