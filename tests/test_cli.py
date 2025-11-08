import sys
from types import SimpleNamespace

import pytest

from xnat_pipelines import cli


def test_cli_run_parses_json(monkeypatch):
    recorded = {}

    class DummyJob:
        def __init__(self):
            self.status = "Complete"

        def wait(self):
            return self

        def stdout_tail(self, n=2000):
            return "logs"

    class DummyExecutor:
        def __init__(self, mode):
            self.mode = mode

        def run(self, **kwargs):
            recorded.update(kwargs)
            return DummyJob()

    monkeypatch.setattr(cli, "Executor", DummyExecutor)

    args = [
        "xnat-pipelines",
        "run",
        "--mode",
        "local",
        "--command",
        "debug",
        "--level",
        "experiment",
        "--id",
        "XNAT_E1",
        "--inputs",
        '{"message":"hello"}',
        "--io",
        '{"upload":false}',
    ]
    monkeypatch.setattr(sys, "argv", args)

    cli.main()

    assert recorded["inputs"] == {"message": "hello"}
    assert recorded["io"] == {"upload": False}
    assert recorded["context"] == {"level": "experiment", "id": "XNAT_E1"}


def test_cli_batch_queue_mode_invokes_run_queue(monkeypatch):
    class DummyBatchRunner:
        def __init__(self, executor, concurrency, retry):
            self.executor = executor
            self.retry = retry
            self.concurrency = concurrency
            self.run_queue_called = False

        def run_queue(self, **kwargs):
            self.run_queue_called = True
            DummyBatchRunner.invocation = kwargs
            return [SimpleNamespace(context=kwargs["contexts"][0], status="Complete", backend="local", error=None)]

        def summary(self, results):
            return f"Batch summary: total={len(results)}, succeeded={len(results)}, failed=0"

    class DummyExecutor:
        def __init__(self, mode):
            self.mode = mode

        def run(self, **kwargs):
            raise AssertionError("Executor.run should not be called directly in this test")

    monkeypatch.setattr(cli, "Executor", DummyExecutor)
    monkeypatch.setattr(cli, "BatchRunner", lambda executor, concurrency, retry: DummyBatchRunner(executor, concurrency, retry))

    args = [
        "xnat-pipelines",
        "batch",
        "--mode",
        "local",
        "--command",
        "debug",
        "--contexts",
        '[{"level":"experiment","id":"E1"}]',
        "--inputs",
        '{"sleep":1}',
        "--queue-mode",
        "--poll-interval",
        "0.1",
        "--job-timeout",
        "30",
    ]
    monkeypatch.setattr(sys, "argv", args)

    cli.main()

    invocation = DummyBatchRunner.invocation
    assert invocation["command_ref"] == "debug"
    assert invocation["contexts"] == [{"level": "experiment", "id": "E1"}]
    assert invocation["poll_interval"] == 0.1
    assert invocation["job_timeout"] == 30
