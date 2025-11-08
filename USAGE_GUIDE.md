# XNAT Pipelines Companion Package v1.0.0

This bundle includes everything you need to run, monitor, and manage local or remote XNAT Container Service workflows from Python, the CLI, or JupyterHub.

## Contents
- `src/xnat_pipelines/` – Companion Python package
- `examples/` – Dashboard and notebook examples (bundled in the wheel/sdist under `xnat_pipelines/examples`)
- `xnat_pipelines_monitoring_jupyterhub.ipynb` – JupyterHub monitoring notebook
- `README.md` – General usage overview
- `LICENSE` – MIT license

## What's New in v1.0.0
| Update | Impact |
|--------|--------|
| Queue execution mode | `BatchRunner.run_queue` and `xnat-pipelines batch --queue-mode` keep a fixed number of jobs in flight with live status polling and per-job timing. |
| Expanded examples | New Example 8 (local dry-run queue) and Example 9 (remote scan queue) illustrate the execution pattern end-to-end. |

## Key Features (v1.x)
| Feature | Description |
|----------|--------------|
| Dual-mode execution | Run containers remotely via XNAT or locally via Docker/Podman. |
| Auto I/O staging | Download inputs / upload outputs to XNAT automatically. |
| Resource filtering | Filter resources by name or filename patterns. |
| Schema-aware mapping | Inputs automatically mapped via XNAT command JSON (env/args/mounts). |
| Batch execution | Run multiple contexts concurrently with retry & monitoring. |
| Dashboard | Web-based monitor with live progress and log tails. |
| JupyterHub notebook | In-notebook live view of local runs with charts. |

## Installation
### From PyPI (recommended)
```bash
pip install xnat-pipelines
```
This installs the package plus all example dashboards and notebooks as package data.

### From source
```bash
pip install -e .
```
Use this when developing against a local checkout.

## Verifying Packaged Examples
After installation you can confirm where the packaged examples live:
```bash
python - <<'PY'
from importlib.resources import files
print(files("xnat_pipelines.examples"))
PY
```
The printed path contains the dashboard static assets and `xnat_pipelines_monitoring_jupyterhub.ipynb`.

## Checking Installed Versions
- CLI:
  ```bash
  xnat-pipelines --version
  ```
- Dashboard:
  ```bash
  xnat-pipelines-dashboard --version
  ```

## Queue Execution Mode
- CLI queue processing with live polling:
  ```bash
  xnat-pipelines batch \
    --queue-mode \
    --contexts '[{"level":"experiment","id":"XNAT_E1"}, {"level":"experiment","id":"XNAT_E2"}]' \
    --command ghcr.io/xnat/debug-command:latest \
    --inputs '{"message":"from queue"}' \
    --concurrency 3 \
    --poll-interval 1.5
  ```
- Python API (throttled queue):
  ```python
  from xnat_pipelines.batch import BatchRunner
  runner = BatchRunner(executor, concurrency=3)
  results = runner.run_queue(
      xnat_session=xn,
      command_ref="dcm2niix",
      contexts=contexts,
      inputs={"bids": "y"},
      poll_interval=2.0,
  )
  print(runner.summary(results))
  ```

## CLI Examples
- List available container commands:
  ```bash
  xnat-pipelines list-commands --url https://xnat.example.org --token $TOKEN
  ```
- Run a container (auto mode):
  ```bash
  xnat-pipelines run \
    --mode auto \
    --url https://xnat.example.org --token $TOKEN \
    --command totalsegmentator:latest \
    --level experiment --id XNAT_E12345 \
    --inputs '{"threshold":"0.3"}'
  ```
- Run a batch:
  ```bash
  xnat-pipelines batch \
    --mode auto \
    --url https://xnat.example.org --token $TOKEN \
    --command totalsegmentator:latest \
    --contexts '[{"level":"experiment","id":"XNAT_E1"},{"level":"experiment","id":"XNAT_E2"}]' \
    --io '{"download":true,"upload":true}' \
    --retry '{"max_retries":1}' \
    --concurrency 4
  ```

## Local Dashboard
```bash
xnat-pipelines-dashboard --runs ./xnat_local_runs --port 8080
```
Then open [http://localhost:8080](http://localhost:8080) in your browser for live job monitoring.

## JupyterHub Monitoring
Open `xnat_pipelines_monitoring_jupyterhub.ipynb` inside your JupyterHub environment and run the notebook. It scans `./xnat_local_runs`, displays job tables, log tails, and simple charts. Press `Stop` to exit the live refresh loop.

## Support & Customization
- Extend `schema_mapping.py` to match your site's Container Service schema.
- Customize dashboard templates under `examples/dashboard_static/`.
- License: MIT (free to modify and redistribute).

## Authentication shortcuts
- The CLI inspects `~/.netrc` (or the path pointed to by the `NETRC` env var) when `--user/--password/--token` are omitted. Add a stanza such as `machine demo02.xnatworks.io login admin password admin` and every `xnat-pipelines ... --url https://demo02.xnatworks.io` invocation will reuse those credentials automatically.

---
**Author:** XNATWorks  
**Email:** info@xnatworks.io  
**Version:** 1.0.0 (2025-11-06)
