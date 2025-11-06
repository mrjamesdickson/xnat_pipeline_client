# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`xnat_pipelines` is a Python companion package for running XNAT Container Service workflows. It provides dual-mode execution (remote via XNAT REST API or local via Docker/Podman), batch processing with concurrency control, I/O staging, and a monitoring dashboard.

## Installation & Setup

```bash
pip install -e .
```

This installs two CLI entrypoints:
- `xnat-pipelines` - main CLI for running containers
- `xnat-pipelines-dashboard` - web-based monitoring dashboard

## Common Commands

### Running Containers

**List available commands:**
```bash
xnat-pipelines list-commands --url https://xnat.example.org --token $TOKEN
```

**Run single container (auto mode selects remote/local):**
```bash
xnat-pipelines run \
  --mode auto \
  --url https://xnat.example.org \
  --token $TOKEN \
  --command totalsegmentator:latest \
  --level experiment \
  --id XNAT_E12345 \
  --inputs '{"threshold":"0.3"}'
```

**Run batch across multiple contexts:**
```bash
xnat-pipelines batch \
  --mode auto \
  --url https://xnat.example.org \
  --token $TOKEN \
  --command totalsegmentator:latest \
  --contexts '[{"level":"experiment","id":"E1"},{"level":"experiment","id":"E2"}]' \
  --io '{"download":true,"upload":true}' \
  --concurrency 4
```

**Launch monitoring dashboard:**
```bash
xnat-pipelines-dashboard --runs ./xnat_local_runs --port 8080
```

### Testing

```bash
python -m pytest tests/
```

## Architecture

### Execution Flow

1. **CLI** (`cli.py`) - Parses arguments, creates XNAT session, delegates to Executor
2. **Executor** (`executor.py`) - Selects backend (remote/local/auto), handles retry logic
3. **Backends** - Execute jobs and return JobHandle:
   - **RemoteBackend** (`backends/remote.py`) - Launches via XNAT REST API (`/xapi/commands/{id}/launch`)
   - **LocalBackend** (`backends/local.py`) - Runs Docker/Podman locally with schema-aware input mapping
4. **JobHandle** - Unified interface for status, wait, logs, and cancellation

### Key Components

**ContainerClient** (`containers.py`)
- Discovers available XNAT container commands via REST API
- Route customization via `routes` dict (defaults to `/xapi/commands`)
- Returns `ContainerCommand` dataclass with id, name, version, image, and raw JSON

**Schema Mapping** (`schema_mapping.py`)
- Reads XNAT command JSON schema (`inputs`, `mounts`)
- Translates user inputs to container env vars or CLI args
- Maps I/O mount points (default: `/input`, `/output`)
- Used by LocalBackend to achieve parity with remote execution

**I/O Staging** (`io_utils.py`)
- `stage_from_xnat()` - Downloads resources from XNAT to local `input/` dir
  - Supports filtering by resource names and filename patterns
  - Handles project/subject/experiment/scan/resource levels
- `upload_outputs_to_xnat()` - Uploads `output/` dir back to XNAT as a resource
  - Creates resource if missing, uploads all files recursively

**Batch Execution** (`batch.py`)
- `BatchRunner` - Runs multiple contexts concurrently using ThreadPoolExecutor
- Returns `BatchResult` list with status, job_id, backend, errors
- Retry logic delegated to Executor per-job

**Dashboard** (`dashboard.py`)
- Lightweight HTTP server serving static HTML/JS
- Scans `--runs` directory for `run.json` and `run.log` files
- `/status.json` endpoint provides job states and log tails
- No external dependencies (uses stdlib `http.server`)

### Execution Modes

- **remote**: Launch on XNAT Container Service, poll status via REST API
- **local**: Run Docker/Podman locally, stage I/O from/to XNAT if `--url` provided
- **auto**: Choose remote if XNAT session provided, else local

### Local Run Directory Structure

```
xnat_local_runs/
  run_1730900000/
    context.json       # XNAT context (level, id)
    run.json           # Job manifest (command, inputs, timestamp)
    run.log            # Container stdout/stderr
    input/             # Downloaded XNAT resources (if io.download=true)
    output/            # Container outputs (uploaded if io.upload=true)
```

### Retry Behavior

Retry config (passed to `--retry` as JSON):
- `max_retries` (int, default 0)
- `backoff` ("fixed" | "exp", default "exp")
- `base_sec` (int, default 2)
- `cap_sec` (int, default 60)

Applied per-job by Executor before backend run.

## Related Resources

- XNAT source code: `../xnat-web` (per global CLAUDE.md)
- Example data files: `../data` (per global CLAUDE.md)
- JupyterHub monitoring notebook: `src/xnat_pipelines/examples/xnat_pipelines_monitoring_jupyterhub.ipynb`

## Python API Usage

```python
import xnat
from xnat_pipelines.executor import Executor

with xnat.connect(url, user=user, password=password) as xn:
    executor = Executor(mode="auto")
    job = executor.run(
        xnat_session=xn,
        command_ref="dcm2niix:latest",
        context={"level": "experiment", "id": "XNAT_E00123"},
        inputs={"compress": "y"},
        io={"download": True, "upload": True}
    )
    job.wait()
    print(job.status)
    print(job.stdout_tail())
```

## Customization Notes

- **Schema mapping**: Extend `schema_mapping.py` for site-specific command schemas
- **Routes**: Pass `--routes '{"commands":"/custom/path"}'` to override XNAT API endpoints
- **Dashboard templates**: Modify `examples/dashboard_static/` for custom UI
- **Resource filtering**: Use `io.resource_filters` with `resource_names` list and `patterns` (fnmatch) for selective I/O staging
