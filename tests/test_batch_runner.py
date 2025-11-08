from types import SimpleNamespace

from xnat_pipelines.batch import BatchRunner, BatchResult
from xnat_pipelines.executor import JobHandle


class DummyJobImpl:
    def __init__(self):
        self._status = "Running"
        self.artifact_ref = None

    def status(self):
        return self._status

    def refresh(self):
        self._status = "Complete"

    def wait(self, timeout=0, poll=0):
        self._status = "Complete"
        return self

    def stdout_tail(self, n=0):
        return ""

    def cancel(self):
        return None


class DummyExecutor:
    mode = "local"

    def __init__(self):
        self.calls = 0

    def run(self, **_):
        self.calls += 1
        return JobHandle(backend="local", job_id=str(self.calls), _impl=DummyJobImpl())


def test_batch_runner_queue(monkeypatch):
    execu = DummyExecutor()
    runner = BatchRunner(executor=execu, concurrency=1)
    contexts = [{"level": "experiment", "id": "XNAT_E1"}, {"level": "experiment", "id": "XNAT_E2"}]
    events = []

    results = runner.run_queue(
        xnat_session=SimpleNamespace(),
        command_ref="cmd",
        contexts=contexts,
        poll_interval=0,
        job_timeout=5,
        status_callback=lambda event: events.append((event.event, event.context["id"], event.status)),
    )

    assert len(results) == 2
    assert all(isinstance(r, BatchResult) for r in results)
    assert {r.status for r in results} == {"Complete"}
    assert execu.calls == 2
    submitted = [e for e in events if e[0] == "submitted"]
    assert len(submitted) == 2
