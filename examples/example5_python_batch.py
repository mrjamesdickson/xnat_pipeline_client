"""Example 5 from EXAMPLE_USAGE.md: Python API batch run (dry-run)."""

from __future__ import annotations

from pathlib import Path

from xnat_pipelines.batch import BatchRunner
from xnat_pipelines.executor import Executor


def main(run_root: str = "demo_runs") -> None:
    workdir = Path(run_root) / "example5_python_batch"
    workdir.mkdir(parents=True, exist_ok=True)

    executor = Executor(mode="local")
    batch_runner = BatchRunner(executor=executor, concurrency=3, retry={"max_retries": 1})

    contexts = [
        {"level": "experiment", "id": "XNAT_E100"},
        {"level": "experiment", "id": "XNAT_E200"},
        {"level": "experiment", "id": "XNAT_E300"},
    ]

    results = batch_runner.run_many(
        xnat_session=None,
        command_ref="ghcr.io/xnat/debug-command:latest",
        contexts=contexts,
        inputs={"message": "Hello from batch", "sleep": 1},
        workdir=str(workdir),
        dry_run=True,
    )

    print(batch_runner.summary(results))
    for res in results:
        run_dir = workdir / res.job_id if res.job_id else None
        print(f"{res.context['id']} -> {res.status} (job: {res.job_id})")
        if run_dir and run_dir.exists():
            print(f"  manifest: {run_dir / 'run.json'}")


if __name__ == "__main__":
    main()
