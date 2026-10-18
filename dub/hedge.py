"""Hedged calls: when a request is slow, send the same request again; the first answer wins.

Gemini latency has a long tail (2026-10-18, six identical one-line calls: 1.3-3.9 s for four, 30-37 s for two),
and a job makes hundreds of calls, so the slowest few set its length. A duplicate after a delay cuts that tail
for the price of the occasional extra call. The losing request is left to finish; its answer is dropped."""
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

_pool = ThreadPoolExecutor(128, thread_name_prefix="hedge")


def first(fn, after: tuple[float, ...] = (15.0, 40.0)):
    """fn() now, again at each delay in `after` (seconds from the start) while nothing has answered.
    Only slowness starts a duplicate: a failure is raised once no attempt is still running, so the caller's
    retry policy (backoff, permanent errors) stays in charge."""
    futures, pending, error, t0 = [_pool.submit(fn)], list(after), None, time.monotonic()
    while futures:
        timeout = max(0.0, t0 + pending[0] - time.monotonic()) if pending else None
        done, _ = wait(futures, timeout=timeout, return_when=FIRST_COMPLETED)
        for f in done:
            futures.remove(f)
            if f.exception() is None:
                return f.result()
            error = f.exception()
        if pending and not done:
            pending.pop(0)
            futures.append(_pool.submit(fn))
    raise error
