from types import SimpleNamespace

import pytest

from xnat_pipelines.executor import Executor, JobHandle


class DummyJob:
    def __init__(self, status="Complete"):
        self._status = status
        self.artifact_ref = None

    def status(self):
        return self._status

    def wait(self, timeout=0, poll=0):
        return self

    def stdout_tail(self, n=0):
        return ""

    def cancel(self):
        return None

    def refresh(self):
        return None


class DummyBackend:
    calls = 0
    should_fail_first = False

    def __init__(self, *_, **__):
        pass

    def run(self, **_):
        type(self).calls += 1
        if self.should_fail_first and type(self).calls == 1:
            raise RuntimeError("boom")
        return JobHandle(backend="dummy", job_id="1", _impl=DummyJob())


def test_executor_auto_mode_prefers_remote(monkeypatch):
    class RemoteStub(DummyBackend):
        calls = 0

    class LocalStub(DummyBackend):
        calls = 0

    monkeypatch.setattr("xnat_pipelines.executor.RemoteBackend", RemoteStub)
    monkeypatch.setattr("xnat_pipelines.executor.LocalBackend", LocalStub)

    execu = Executor(mode="auto")
    handle = execu.run(xnat_session=SimpleNamespace(), command_ref="cmd", context={"level": "experiment", "id": "XNAT_E1"})

    assert handle.backend == "dummy"
    assert RemoteStub.calls == 1
    assert LocalStub.calls == 0


def test_executor_retry_on_failure(monkeypatch):
    class FlakyBackend(DummyBackend):
        should_fail_first = True

    monkeypatch.setattr("xnat_pipelines.executor.RemoteBackend", FlakyBackend)
    monkeypatch.setattr("xnat_pipelines.executor.LocalBackend", FlakyBackend)
    monkeypatch.setattr("xnat_pipelines.executor.time.sleep", lambda *_: None)

    execu = Executor(mode="remote")
    handle = execu.run(
        xnat_session=SimpleNamespace(),
        command_ref="cmd",
        context={"level": "experiment", "id": "XNAT_E1"},
        retry={"max_retries": 1, "base_sec": 0},
    )

    assert handle.backend == "dummy"
    assert FlakyBackend.calls == 2
