# Quick-Start Runs

The shell and Python snippets in `EXAMPLE_USAGE.md` now live here as runnable scripts. They default to `--dry-run` so Docker/Podman is not required; remove that flag when you're ready to execute real containers.

- `example1_local_dry_run.sh` — single debug container (CLI).
- `example2_dcm2niix_dry_run.sh` — dcm2niix invocation preview (CLI).
- `example3_batch_dry_run.sh` — batch three contexts with the debug container (CLI).
- `example4_python_single.py` — Python API single run.
- `example5_python_batch.py` — Python API batch run.
- `example6_remote_debug.py` — remote launch against the demo02.xnatworks.io Container Service (REST API).
- `example7_remote_dcm2niix.py` — remote dcm2niix launches for every DICOM-backed scan in a project.

All scripts accept an optional first argument pointing at the parent directory where run manifests should be written. By default they use `./demo_runs/`.

For the Python examples that call the remote XNAT service, activate the repo virtualenv first (e.g. `source venv/bin/activate`) or invoke them via `venv/bin/python`.

`example6_remote_debug.py` also includes helper flags:
- `--list-containers` (with `--containers-limit`) to show recent container IDs/status.
- `--sample-from-id <id>` to print a ready-to-edit Python snippet that relaunches a given container via `Executor`.
