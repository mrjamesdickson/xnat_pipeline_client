# XNAT Pipelines Companion Package v0.6.1

This bundle includes everything you need to run, monitor, and manage local or remote XNAT Container Service workflows from Python, the CLI, or JupyterHub.

## Contents
- `src/xnat_pipelines/` – Companion Python package
- `examples/` – Dashboard and notebook examples (bundled in the wheel/sdist under `xnat_pipelines/examples`)
- `xnat_pipelines_monitoring_jupyterhub.ipynb` – JupyterHub monitoring notebook
- `README.md` – General usage overview
- `LICENSE` – MIT license

## What's New in v0.6.1
| Update | Impact |
|--------|--------|
| Packaged examples | The dashboard assets and JupyterHub notebook now ship inside both the wheel and sdist, so `pip install xnat-pipelines` provides the same example files as cloning the repository. |
| No runtime deltas | CLI, API, and dashboard behavior are unchanged from v0.6.0; the release focuses on packaging parity. |

## Key Features (v0.6.x)
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

---
**Author:** XNATWorks  
**Email:** info@xnatworks.io  
**Version:** 0.6.1 (2025-11-06)
