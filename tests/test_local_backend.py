import json
from pathlib import Path
from types import SimpleNamespace

from xnat_pipelines.backends.local import LocalBackend


def test_local_backend_dry_run_writes_manifest(tmp_path):
    backend = LocalBackend(xnat_session=None, workdir=tmp_path, engine="docker", dry_run=True)
    job = backend.run(
        command_ref="ghcr.io/xnat/debug-command:latest",
        context={"level": "experiment", "id": "XNAT_E123"},
        inputs={"message": "hello"},
    )

    run_dir = tmp_path / job.job_id
    manifest = json.loads((run_dir / "run.json").read_text())
    assert manifest["command"] == "ghcr.io/xnat/debug-command:latest"
    assert manifest["context"]["id"] == "XNAT_E123"

    log_text = (run_dir / "run.log").read_text()
    assert log_text.startswith("DRY RUN")


def test_local_backend_uploads_outputs(monkeypatch, tmp_path):
    uploads = {}

    def fake_upload(xn, context, run_dir, resource_name):
        uploads["called_with"] = (xn, context, run_dir, resource_name)
        (run_dir / "output_upload_marker.txt").write_text("uploaded")
        return "experiment:XNAT_E999/resource:processed"

    class DummyProc:
        def __init__(self, *_, **__):
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 1

        def kill(self):
            self.returncode = 1

    fake_client = SimpleNamespace(
        get_command=lambda *_: SimpleNamespace(image="debug-image", raw={"inputs": []})
    )

    monkeypatch.setattr("xnat_pipelines.backends.local.upload_outputs_to_xnat", fake_upload)
    monkeypatch.setattr("xnat_pipelines.backends.local.subprocess.Popen", lambda *args, **kwargs: DummyProc())
    monkeypatch.setattr("xnat_pipelines.backends.local.ContainerClient.from_xnat", lambda *args, **kwargs: fake_client)

    xn = SimpleNamespace()
    backend = LocalBackend(xnat_session=xn, workdir=tmp_path, engine="docker", io={"upload": True, "resource_name": "processed"}, dry_run=False)
    job = backend.run(
        command_ref="debug",
        context={"level": "experiment", "id": "XNAT_E999"},
        inputs={},
    )

    run_dir = tmp_path / job.job_id
    (run_dir / "output" / "result.txt").write_text("data")

    job.wait()

    assert uploads["called_with"][0] is xn
    assert uploads["called_with"][1] == {"level": "experiment", "id": "XNAT_E999"}
    assert uploads["called_with"][3] == "processed"
    assert job.artifact_ref == "experiment:XNAT_E999/resource:processed"
