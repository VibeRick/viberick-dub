import pytest
from dub import gem


@pytest.mark.live
def test_json_call_roundtrip():
    out = gem.json_call("Return the number 7.", {"type": "object", "properties": {"n": {"type": "integer"}},
                                                  "required": ["n"]})
    assert out["n"] == 7
    assert gem.cost() > 0


from types import SimpleNamespace
from unittest.mock import Mock


def fake_client(monkeypatch, responses):
    generate = Mock(side_effect=responses)
    monkeypatch.setattr(gem, "client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(gem.time, "sleep", lambda _: None)
    return generate


def test_json_decode_failure_retries_inside_bounded_call(monkeypatch):
    generate = fake_client(monkeypatch, [SimpleNamespace(text="{broken"), SimpleNamespace(text='{"n": 7}')])
    assert gem.json_call("prompt", {"type": "object"}) == {"n": 7}
    assert generate.call_count == 2


def test_json_decode_retries_are_bounded(monkeypatch):
    import json
    generate = fake_client(monkeypatch, [SimpleNamespace(text="{broken")] * 8)
    with pytest.raises(json.JSONDecodeError):
        gem.json_call("prompt", {"type": "object"})
    assert generate.call_count == 8


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_errors_do_not_retry(monkeypatch, status):
    error = RuntimeError("sensitive response body")
    error.code = status
    generate = fake_client(monkeypatch, [error])
    with pytest.raises(RuntimeError):
        gem.text_call("prompt")
    assert generate.call_count == 1


def test_retry_logs_do_not_echo_provider_secrets(monkeypatch, capsys):
    fake_client(monkeypatch, [RuntimeError("503 proxy=http://name:secret@host?key=secret"), SimpleNamespace(text="ok")])
    assert gem.text_call("prompt") == "ok"
    logs = capsys.readouterr().err
    assert "503" in logs and "secret" not in logs and "host" not in logs
