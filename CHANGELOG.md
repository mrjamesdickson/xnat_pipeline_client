# XNAT Pipelines Companion – Changelog

## v1.0.0 (Queue execution)
- Added `BatchRunner.run_queue` and `QueueEvent` for queue-managed execution with live polling plus duration tracking.
- `xnat-pipelines batch` now accepts `--queue-mode`, `--poll-interval`, and `--job-timeout` to mirror the new API from the CLI.
- Introduced Example 8 (local queue) and Example 9 (remote scan queue) showcasing the new workflow.

## v0.6.1 (Packaging update)
- Include examples and the JupyterHub monitoring notebook inside the **wheel** and **sdist**.
- Added `MANIFEST.in` and `include-package-data = true` in `pyproject.toml`.
- No runtime code changes; version bump only for packaging.

## v0.6.0
- Schema-aware input mapping, HTML dashboard, JupyterHub notebook, examples and docs.

## v0.5.0
- Schema-aware local execution, dashboard entrypoint, run manifest/log standardization.

## v0.4.0
- Full I/O staging across all context levels; resource filters.

## v0.3.0
- Batch execution, retries, auto I/O staging.

## v0.2.0
- Dual-mode execution (remote/local) with unified API.

## v0.1.0
- Initial release with container discovery and demo notebook.
