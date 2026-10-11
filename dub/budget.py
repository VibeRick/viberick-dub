"""Thread-safe local spending estimates, not a provider-enforced billing limit.

Admission reserves an allowance BEFORE each external attempt. Unknown/failed
requests keep it because failure does not establish that a provider charged $0.
Explicit settlement can replace it with a measured charge. A higher settlement
is recorded honestly and blocks later requests; it cannot undo provider billing.
"""
from decimal import Decimal, ROUND_CEILING
import threading
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


class BudgetExceeded(RuntimeError):
    code = 400  # Existing Gemini retry policy treats this local refusal as terminal.


def _money(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amounts must be finite and nonnegative")
    return amount.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)


class Ticket:
    def __init__(self, ledger, ident):
        self.ledger, self.ident = ledger, ident

    def settle(self, actual_usd) -> None:
        self.ledger.settle(self.ident, actual_usd)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        # Reservations intentionally remain charged after unknown failures.
        return False


class Budget:
    def __init__(self, cap_usd, max_calls: dict[str, int], ledger_path: Path | None = None, run_cap_usd=None):
        self.cap = _money(cap_usd)
        if self.cap <= 0 or not max_calls or any(type(v) is not int or v <= 0 for v in max_calls.values()):
            raise ValueError("Positive budget and per-provider call limits are required")
        self.max_calls = dict(max_calls)
        self.calls = dict.fromkeys(max_calls, 0)
        self.records = []
        self._lock = threading.Lock()
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.run_cap = _money(run_cap_usd) if run_cap_usd is not None else self.cap
        if self.run_cap <= 0:
            raise ValueError("Run allowance must be positive")
        self.run_committed = Decimal(0)
        with self._transaction():
            pass

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self.ledger_path is None:
                yield
                return
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.with_suffix(self.ledger_path.suffix + ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    if self.ledger_path.exists():
                        state = json.loads(self.ledger_path.read_text())
                        if _money(state["budget_usd"]) != self.cap or state["call_limits"] != self.max_calls:
                            raise ValueError("Shared ledger budget/call limits differ; reuse the existing approved limits")
                        self.records = [{**r, "amount": _money(r["amount"])} for r in state["attempts"]]
                        self.calls = {provider: sum(r["provider"] == provider for r in self.records) for provider in self.max_calls}
                    yield
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _persist(self):
        if self.ledger_path is None:
            return
        state = self._snapshot()
        descriptor, name = tempfile.mkstemp(prefix=self.ledger_path.name + ".", dir=self.ledger_path.parent)
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump(state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.ledger_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def reserve(self, provider: str, estimate_usd) -> Ticket:
        estimate = _money(estimate_usd)
        if estimate <= 0:
            raise ValueError("Each request must reserve a positive allowance")
        with self._transaction():
            if provider not in self.max_calls:
                raise BudgetExceeded("Provider has no configured call limit")
            total = sum((r["amount"] for r in self.records), Decimal(0))
            if self.calls[provider] >= self.max_calls[provider] or total + estimate > self.cap or self.run_committed + estimate > self.run_cap:
                raise BudgetExceeded(f"Local estimated spending/call limit reached for {provider}; request not sent")
            ident = len(self.records)
            self.records.append({"provider": provider, "amount": estimate, "settled": False})
            self.calls[provider] += 1
            self.run_committed += estimate
            self._persist()
            return Ticket(self, ident)

    def settle(self, ident: int, actual_usd) -> None:
        actual = _money(actual_usd)
        with self._transaction():
            record = self.records[ident]
            if record["settled"]:
                raise ValueError("Ticket already settled")
            self.run_committed += actual - record["amount"]
            record.update(amount=actual, settled=True)
            self._persist()

    def snapshot(self) -> dict:
        with self._transaction():
            return self._snapshot()

    def _snapshot(self) -> dict:
        total = sum((r["amount"] for r in self.records), Decimal(0))
        return {"kind": "local estimated spending stop, not a provider billing hard cap",
                "budget_usd": float(self.cap), "committed_usd": float(total),
                "remaining_usd": float(max(Decimal(0), self.cap - total)),
                "run_budget_usd": float(self.run_cap), "run_committed_usd": float(self.run_committed),
                "over_budget": total > self.cap, "calls": dict(self.calls),
                "call_limits": dict(self.max_calls),
                "attempts": [{**r, "amount": float(r["amount"])} for r in self.records]}
