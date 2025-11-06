"""Example 4 from EXAMPLE_USAGE.md: Python API single run (dry-run)."""

from __future__ import annotations

import json
from pathlib import Path

from xnat_pipelines.executor import Executor


def main(run_root: str = "demo_runs") -> None:
    workdir = Path(run_root) / "example4_python_single"
    workdir.mkdir(parents=True, exist_ok=True)

    executor = Executor(mode="local")
    job = executor.run(
        xnat_session=None,
        command_ref="ghcr.io/xnat/debug-command:latest",
        context={"level": "experiment", "id": "XNAT_E00123"},
        inputs={"message": "Hello from Python", "sleep": 1, "should_fail": False},
        workdir=str(workdir),
        dry_run=True,
    )

    job.wait()
    print(f"Job status: {job.status}")

    run_dir = workdir / job.job_id
    manifest = json.loads((run_dir / "run.json").read_text())
    print(f"Run manifest: {run_dir}")
    print("Docker preview:", " ".join(manifest["cmd"]))


if __name__ == "__main__":
    main()
