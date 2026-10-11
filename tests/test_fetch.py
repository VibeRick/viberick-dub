import re
from dub import fetch


def test_cmd_limits_section_and_height_when_partial():
    cmd = fetch._cmd("https://youtu.be/x", "/tmp/o.%(ext)s", max_sec=180, proxy=None)
    assert "--download-sections" in cmd and "*0-182" in cmd
    assert any("height<=720" in c for c in cmd)


def test_cmd_uses_proxy_when_given():
    cmd = fetch._cmd("https://youtu.be/x", "/tmp/o.%(ext)s", max_sec=None, proxy="http://p:1")
    assert cmd[cmd.index("--proxy") + 1] == "http://p:1"


import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


@pytest.mark.parametrize("metadata", [
    {"duration": None}, {"duration": 0}, {"duration": float("inf")},
    {"duration": 10, "is_live": True}, {"duration": 10, "live_status": "is_upcoming"},
])
def test_unsupported_duration_or_live_fails_before_conversion(tmp_path, monkeypatch, metadata):
    (tmp_path / "source.info.json").write_text(json.dumps(metadata))
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(fetch.subprocess, "run", run)
    with pytest.raises(ValueError, match="finished video"):
        fetch.fetch("https://youtu.be/test", tmp_path)
    assert run.call_count == 1
    assert run.call_args.args[0][0] == "yt-dlp"


def test_download_error_never_exposes_proxy_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DUB_PROXY", "http://user:secret@proxy")
    run = Mock(return_value=SimpleNamespace(returncode=1, stderr="ERROR: http://user:secret@proxy"))
    monkeypatch.setattr(fetch.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="Check that it is public") as error:
        fetch.fetch("https://youtu.be/test", tmp_path)
    assert "secret" not in str(error.value)
    assert run.call_count == 1 + fetch.PROXY_ATTEMPTS


def test_rotating_webshare_user_becomes_a_sticky_session_per_attempt():
    s = fetch.sticky("http://acct-rotate:pw@p.webshare.io:80")
    assert re.fullmatch(r"http://acct-\d+:pw@p\.webshare\.io:80", s)
    assert fetch.sticky("http://plain:pw@host:1") == "http://plain:pw@host:1"
    assert fetch._redact("ERROR via http://acct-7:pw@p.webshare.io:80") == "ERROR via http://***@p.webshare.io:80"
