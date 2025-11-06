# XNAT Pipelines Companion Package v0.6.0

This bundle includes everything you need to run, monitor, and manage local or remote XNAT Container Service workflows from Python, CLI, or JupyterHub.

## Contents
- `src/xnat_pipelines/` – Companion Python package
- `examples/` – Dashboard and notebook examples
- `xnat_pipelines_monitoring_jupyterhub.ipynb` – JupyterHub monitoring notebook
- `README.md` – General usage
- `LICENSE` – MIT license

## Key Features (v0.6.0)
| Feature | Description |
|----------|--------------|
| Dual-mode execution | Run containers remotely via XNAT or locally via Docker/Podman |
| Auto I/O staging | Download inputs / upload outputs to XNAT |
| Resource filtering | Filter resources by name or filename patterns |
| Schema-aware mapping | Inputs automatically mapped via XNAT command JSON (env/args/mounts) |
| Batch execution | Run multiple contexts concurrently with retry & monitoring |
| Dashboard | Web-based monitor with live progress and log tails |
| JupyterHub notebook | In-notebook live view of all local runs with charts |

## Installation
```bash
pip install -e .
```

## CLI Examples

List available container commands:
```bash
xnat-pipelines list-commands --url https://xnat.example.org --token $TOKEN
```

Run a container (auto mode):
```bash
xnat-pipelines run --mode auto   --url https://xnat.example.org --token $TOKEN   --command totalsegmentator:latest   --level experiment --id XNAT_E12345   --inputs '{"threshold":"0.3"}'
```

Run a batch:
```bash
xnat-pipelines batch   --mode auto   --url https://xnat.example.org --token $TOKEN   --command totalsegmentator:latest   --contexts '[{"level":"experiment","id":"XNAT_E1"},{"level":"experiment","id":"XNAT_E2"}]'   --io '{"download":true,"upload":true}'   --retry '{"max_retries":1}'   --concurrency 4
```

## Local Dashboard
```bash
xnat-pipelines-dashboard --runs ./xnat_local_runs --port 8080
```
Then open [http://localhost:8080](http://localhost:8080) in your browser.

## JupyterHub Monitoring
Open `xnat_pipelines_monitoring_jupyterhub.ipynb` in your JupyterHub server and run it.
It scans `./xnat_local_runs`, displays job tables, log tails, and simple charts.
Press `Stop` to exit the live refresh loop.

## Support & Customization
- Extend `schema_mapping.py` to match your site's Container Service schema.
- Customize dashboard templates under `examples/dashboard_static/`.
- License: MIT (free to modify and redistribute).

---
**Author:** XNATWorks  
**Email:** info@xnatworks.io  
**Version:** 0.6.0 (2025-11-06)
