from dub import fetch


def test_cmd_limits_section_and_height_when_partial():
    cmd = fetch._cmd("https://youtu.be/x", "/tmp/o.%(ext)s", max_sec=180, proxy=None)
    assert "--download-sections" in cmd and "*0-182" in cmd
    assert any("height<=720" in c for c in cmd)


def test_cmd_uses_proxy_when_given():
    cmd = fetch._cmd("https://youtu.be/x", "/tmp/o.%(ext)s", max_sec=None, proxy="http://p:1")
    assert cmd[cmd.index("--proxy") + 1] == "http://p:1"
