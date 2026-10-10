from dub import worker


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
