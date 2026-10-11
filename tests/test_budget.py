from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dub.budget import Budget, BudgetExceeded


def test_concurrent_admission_cannot_overbook():
    budget = Budget(1, {"tts": 100})
    def admit(_):
        try:
            budget.reserve("tts", .1)
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(20) as pool:
        assert sum(pool.map(admit, range(100))) == 10
    assert budget.snapshot()["committed_usd"] == 1


def test_failed_call_retains_reservation():
    budget = Budget(.1, {"tts": 2})
    with pytest.raises(RuntimeError):
        with budget.reserve("tts", .1):
            raise RuntimeError("unknown provider failure")
    with pytest.raises(BudgetExceeded):
        budget.reserve("tts", .1)


def test_settlement_releases_only_measured_difference_and_keeps_call_count():
    budget = Budget(1, {"tts": 1, "text": 2})
    ticket = budget.reserve("tts", .5)
    ticket.settle(.2)
    budget.reserve("text", .8)
    assert budget.snapshot()["committed_usd"] == 1
    with pytest.raises(BudgetExceeded):
        budget.reserve("tts", .01)
    with pytest.raises(ValueError):
        ticket.settle(0)


def test_underestimated_actual_is_honestly_recorded_and_stops_future_calls():
    budget = Budget(1, {"tts": 10})
    budget.reserve("tts", .5).settle(2)
    assert budget.snapshot()["over_budget"]
    with pytest.raises(BudgetExceeded):
        budget.reserve("tts", .1)


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1, 0])
def test_invalid_reservations_rejected(amount):
    with pytest.raises(ValueError):
        Budget(1, {"tts": 2}).reserve("tts", amount)


def test_guards_stop_actual_attempts_before_network_and_restore_functions(monkeypatch):
    from dub import gem, voice
    from tools.validate_voice import guarded_requests
    generate = Mock(return_value=SimpleNamespace(usage_metadata=None))
    client = lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    opener = Mock(return_value="response")
    monkeypatch.setattr(gem, "client", client)
    monkeypatch.setattr(voice.urllib.request, "urlopen", opener)
    budget = Budget(.15, {"text": 1, "tts": 1})
    with guarded_requests(budget, .1, .05):
        gem.client().models.generate_content(model="fake")
        voice.urllib.request.urlopen(SimpleNamespace(full_url=voice.URL))
        with pytest.raises(BudgetExceeded):
            voice.urllib.request.urlopen(SimpleNamespace(full_url=voice.URL))
        with pytest.raises(BudgetExceeded):
            gem.client().models.generate_content(model="fake")
    assert generate.call_count == opener.call_count == 1
    assert gem.client is client and voice.urllib.request.urlopen is opener


def test_inner_retry_network_failures_are_each_counted(monkeypatch):
    from dub import gem, voice
    from tools.validate_voice import guarded_requests
    opener = Mock(side_effect=TimeoutError("network uncertainty"))
    monkeypatch.setattr(voice.urllib.request, "urlopen", opener)
    monkeypatch.setattr(voice.config, "tts_key", lambda: "dummy")
    monkeypatch.setattr(voice.GATE, "wait", lambda: None)
    monkeypatch.setattr(voice.time, "sleep", lambda _: None)
    budget = Budget(.1, {"tts": 10, "text": 10})
    with guarded_requests(budget, .05, .05):
        with pytest.raises(BudgetExceeded):
            voice._request("hello", "Puck", "en")
    assert opener.call_count == 2
    assert budget.snapshot()["calls"]["tts"] == 2


def test_dry_run_never_reads_keys_or_writes_outputs(tmp_path, monkeypatch, capsys):
    from dub import config
    from tools import validate_voice
    source = tmp_path / "run"
    (source / "out").mkdir(parents=True)
    for name, data in {"units.json": [{"id": 1, "text": "hello"}], "brief.json": {}, "cast.json": {},
                       "out/report.json": {"src": "ko", "duration": 180}}.items():
        (source / name).write_text(json.dumps(data))
    def forbidden():
        raise AssertionError("credential access in dry run")
    monkeypatch.setattr(config, "tts_key", forbidden)
    monkeypatch.setattr(config, "gemini_key", forbidden)
    out = tmp_path / "validation"
    monkeypatch.setattr("sys.argv", ["validate_voice", str(source), "--output", str(out)])
    validate_voice.main()
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["line_language_pairs"] == 3


def test_shared_ledger_admits_atomically_across_instances_and_preserves_failures(tmp_path):
    path = tmp_path / "budget.json"
    a = Budget(1, {"tts": 10}, ledger_path=path)
    b = Budget(1, {"tts": 10}, ledger_path=path)
    a.reserve("tts", .6)
    with pytest.raises(BudgetExceeded):
        b.reserve("tts", .6)
    b.reserve("tts", .4)
    assert a.snapshot()["committed_usd"] == 1
    assert Budget(1, {"tts": 10}, ledger_path=path).snapshot()["calls"]["tts"] == 2


def test_trial_limit_does_not_reset_shared_budget(tmp_path):
    path = tmp_path / "budget.json"
    a = Budget(100, {"tts": 500}, ledger_path=path, run_cap_usd=1)
    a.reserve("tts", 1)
    with pytest.raises(BudgetExceeded):
        a.reserve("tts", .1)
    b = Budget(100, {"tts": 500}, ledger_path=path, run_cap_usd=1)
    b.reserve("tts", 1)
    assert b.snapshot()["committed_usd"] == 2
    assert b.snapshot()["run_committed_usd"] == 1
    with pytest.raises(ValueError):
        Budget(200, {"tts": 500}, ledger_path=path)
