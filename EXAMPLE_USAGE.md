# xnat_pipelines - Practical Examples

## Overview
This guide demonstrates real-world usage of `xnat_pipelines` with example containers.

→ Ready-to-run helper scripts for each example now live in `examples/`. They default to `--dry-run` so you can preview the manifests without Docker/Podman.

---

## Example 1: Single Container (CLI - Dry Run)

Run a debug container to test the setup without Docker:

```bash
xnat-pipelines run \
  --mode local \
  --command ghcr.io/xnat/debug-command:latest \
  --level experiment \
  --id XNAT_E00123 \
  --inputs '{"message":"Hello XNAT","sleep":"2"}' \
  --workdir ./my_runs \
  --dry-run
```

**What this does:**
- Runs in `local` mode (no XNAT server needed)
- Uses the debug container for testing
- Creates run directories in `./my_runs/`
- `--dry-run` shows the Docker command without executing

---

## Example 2: DICOM to NIfTI Conversion (CLI)

Convert DICOM files to NIfTI format with dcm2niix:

```bash
xnat-pipelines run \
  --mode local \
  --command ghcr.io/xnat/dcm2niix:latest \
  --level experiment \
  --id XNAT_E00456 \
  --inputs '{"compress":"y","bids_sidecar":"y","filename":"%p_%s"}' \
  --workdir ./conversions
```

**With I/O staging from XNAT:**

```bash
xnat-pipelines run \
  --mode auto \
  --url https://xnat.example.org \
  --token $XNAT_TOKEN \
  --command dcm2niix:latest \
  --level experiment \
  --id XNAT_E00456 \
  --inputs '{"compress":"y"}' \
  --io '{"download":true,"upload":true}'
```

**What this does:**
- `--mode auto` uses remote if XNAT available, else local
- Downloads DICOM resources from experiment XNAT_E00456
- Runs dcm2niix conversion
- Uploads NIfTI outputs back to XNAT as a resource

---

## Example 3: Batch Processing (CLI)

Process multiple experiments in parallel:

```bash
xnat-pipelines batch \
  --mode auto \
  --url https://xnat.example.org \
  --token $XNAT_TOKEN \
  --command dcm2niix:latest \
  --contexts '[
    {"level":"experiment","id":"XNAT_E001"},
    {"level":"experiment","id":"XNAT_E002"},
    {"level":"experiment","id":"XNAT_E003"}
  ]' \
  --inputs '{"compress":"y"}' \
  --io '{"download":true,"upload":true}' \
  --concurrency 4 \
  --retry '{"max_retries":2,"backoff":"exp","base_sec":3}'
```

**What this does:**
- Processes 3 experiments concurrently (max 4 at once)
- Retries failed jobs up to 2 times with exponential backoff
- Downloads inputs and uploads outputs for each

---

## Example 4: Python API - Single Run

```python
import xnat
from xnat_pipelines.executor import Executor

# Connect to XNAT
with xnat.connect("https://xnat.example.org", token="your-token") as xn:
    # Create executor (auto mode)
    executor = Executor(mode="auto")
    
    # Run container
    job = executor.run(
        xnat_session=xn,
        command_ref="dcm2niix:latest",
        context={"level": "experiment", "id": "XNAT_E00123"},
        inputs={"compress": "y", "bids_sidecar": "y"},
        io={"download": True, "upload": True}
    )
    
    # Wait and check status
    job.wait(timeout=3600)
    print(f"Status: {job.status}")
    print(f"Logs:\n{job.stdout_tail(n=500)}")
```

---

## Example 5: Python API - Batch Processing

```python
import xnat
from xnat_pipelines.executor import Executor
from xnat_pipelines.batch import BatchRunner

with xnat.connect("https://xnat.example.org", token="your-token") as xn:
    # Setup batch runner
    executor = Executor(mode="auto")
    batch_runner = BatchRunner(
        executor=executor,
        concurrency=4,
        retry={"max_retries": 2, "backoff": "exp"}
    )
    
    # Define contexts
    contexts = [
        {"level": "experiment", "id": "XNAT_E001"},
        {"level": "experiment", "id": "XNAT_E002"},
        {"level": "experiment", "id": "XNAT_E003"},
    ]
    
    # Run batch
    results = batch_runner.run_many(
        xnat_session=xn,
        command_ref="dcm2niix:latest",
        contexts=contexts,
        inputs={"compress": "y"},
        io={"download": True, "upload": True}
    )
    
    # Show summary
    print(batch_runner.summary(results))
    
    # Check individual results
    for r in results:
        print(f"{r.context['id']}: {r.status}")
        if r.error:
            print(f"  Error: {r.error}")
```

---

## Example 6: Remote Launch (REST API)

Use the demo server at `http://demo02.xnatworks.io` to trigger the `debug` container remotely:

Activate the virtualenv first (or run via `venv/bin/python`):

```bash
source venv/bin/activate
python3 examples/example6_remote_debug.py \
  --target-id XNAT_E00001 \
  --message "echo remote from xnat_pipelines" \
  --output-file remote-example.txt \
  --submit
```

**What this does:**
- Authenticates with `admin` / `admin` (override via `--user` / `--password`).
- Calls `/xapi/wrappers/70/launch` to inspect the launch form metadata.
- Posts to `/xapi/wrappers/70/root/xnat:imageSessionData/launch` with the provided inputs.
- Prints the launch response and the most recent container row returned by `/xapi/containers`.

Source overview:

```python
import requests

def resolve_command(session, base_url, command_name):
    resp = session.get(f"{base_url}/xapi/commands", params={"format": "json"})
    resp.raise_for_status()
    # pick the entry where name/id matches

def launch_container(session, base_url, wrapper_id, root_element, root_param, target_id, inputs):
    payload = {"context": root_param, root_param: target_id, "inputs": json.dumps(inputs)}
    for key, value in inputs.items():
        payload[f"inputs.{key}"] = value if isinstance(value, str) else json.dumps(value)
    resp = session.post(f"{base_url}/xapi/wrappers/{wrapper_id}/root/{root_element}/launch", data=payload)
    resp.raise_for_status()
    return resp.json()

with requests.Session() as sess:
    sess.auth = (user, password)
    command = resolve_command(sess, base_url, "debug")
    # select wrapper 70 (session-level)
    report = launch_container(sess, base_url, 70, "xnat:imageSessionData", "session", target_session_id, inputs)

# Optional helpers:
#   python3 examples/example6_remote_debug.py --list-installed   # shows unique container commands installed on the server
#   python3 examples/example6_remote_debug.py --list-running     # shows recent container jobs (id, command, context, status)
#   python3 examples/example6_remote_debug.py --sample-from-id <container_id>
#   xnat-pipelines list-running --url http://demo02.xnatworks.io --user admin --password admin --limit 5
```

Omit `--submit` to preview the launch UI without starting a container.

--- 

## Example 7: Remote dcm2niix Batch (Python)

Run `dcm2niix` against every scan in `Prostate-AEC` that exposes a `DICOM` resource:

Activate the project virtual environment first (or prefix the command with `venv/bin/python`):

```bash
source venv/bin/activate
python3 examples/example7_remote_dcm2niix.py \
  --project Prostate-AEC \
  --bids y \
  --limit 10
```

**What this does:**
- Enumerates experiments and scans via `/data/projects/{project}/experiments` and `/data/experiments/{id}/scans`.
- Filters scans that provide a `DICOM` resource to satisfy the scan wrapper’s pre-resolution step (dcm2niix runs at the scan context).
- Submits each scan to the remote container service using the `Executor(mode="remote")`.

Source overview:

```python
from dataclasses import dataclass
import requests
import xnat
from xnat_pipelines.executor import Executor

@dataclass
class ScanTarget:
    experiment_id: str
    scan_id: str
    label: str | None
    archive_path: str

# ...fetch_scans_with_dicoms(...) gathers all scan archive paths...

with xnat.connect(base_url, user=user, password=password) as xn:
    executor = Executor(mode="remote")
    for target in targets:
        job = executor.run(
            xnat_session=xn,
            command_ref="dcm2niix",
            context={"level": "scan", "id": target.archive_path},
            inputs={"bids": bids_flag, **extra_options},
        )
        job.wait(timeout=600)
        print(target.experiment_id, target.scan_id, job.status)
```

Drop `--limit` to process every qualifying scan; pass `--other-options` to forward extra dcm2niix flags.

---

## Example 8: Monitoring with Dashboard

Start the web dashboard to monitor local runs:

```bash
xnat-pipelines-dashboard --runs ./my_runs --port 8080
```

Then open http://localhost:8080 in your browser to see:
- Live job status
- Log tails
- Run statistics
- Job details (context, inputs, timestamps)

---

## Example 9: Resource Filtering

Download only specific resources or file patterns:

```bash
xnat-pipelines run \
  --mode auto \
  --url https://xnat.example.org \
  --token $XNAT_TOKEN \
  --command my-processor:latest \
  --level experiment \
  --id XNAT_E00123 \
  --io '{
    "download": true,
    "upload": true,
    "resource_filters": {
      "resource_names": ["DICOM", "NIFTI"],
      "patterns": ["*.dcm", "*.nii.gz"]
    }
  }'
```

**Python API:**

```python
job = executor.run(
    xnat_session=xn,
    command_ref="my-processor:latest",
    context={"level": "experiment", "id": "XNAT_E00123"},
    io={
        "download": True,
        "upload": True,
        "resource_filters": {
            "resource_names": ["DICOM"],
            "patterns": ["*.dcm"]
        }
    }
)
```

---

## Example 8: Local-Only Mode (No XNAT)

Run containers locally using your own data directories:

```python
from xnat_pipelines.executor import Executor
import shutil
from pathlib import Path

executor = Executor(mode="local")

# Setup input data
run_dir = Path("./my_runs/manual_run")
run_dir.mkdir(parents=True, exist_ok=True)
input_dir = run_dir / "input"
input_dir.mkdir(exist_ok=True)

# Copy your data to input/
shutil.copy("my_dicoms/file1.dcm", input_dir)
shutil.copy("my_dicoms/file2.dcm", input_dir)

# Run without XNAT
job = executor.run(
    xnat_session=None,  # No XNAT needed
    command_ref="ghcr.io/xnat/dcm2niix:latest",
    context={"level": "local", "id": "manual_run"},
    inputs={"compress": "y"},
    workdir="./my_runs"
)

job.wait()
print(f"Status: {job.status}")

# Check output/
output_dir = run_dir / "output"
print(f"Output files: {list(output_dir.glob('*'))}")
```

---

## Container Schemas

The package automatically maps inputs based on container command schemas:

**debug-command schema:**
```json
{
  "inputs": [
    {"name": "message", "type": "string", "arg": "--message"},
    {"name": "sleep", "type": "int", "arg": "--sleep"},
    {"name": "should_fail", "type": "boolean", "env": "SHOULD_FAIL"}
  ],
  "mounts": {
    "input": "/input",
    "output": "/output"
  }
}
```

When you provide `inputs={"message": "hello", "sleep": "5", "should_fail": "true"}`:
- Generates: `--message hello --sleep 5`
- Sets env: `SHOULD_FAIL=true`
- Mounts volumes at `/input` and `/output`

---

## Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `local` | Always run via Docker/Podman locally | Development, testing, no XNAT server |
| `remote` | Always run via XNAT Container Service | Production XNAT deployment |
| `auto` | Use remote if XNAT session provided, else local | Flexible scripts that work both ways |

---

## Retry Configuration

```python
retry_config = {
    "max_retries": 3,        # Retry up to 3 times
    "backoff": "exp",        # Exponential backoff ("exp" or "fixed")
    "base_sec": 2,           # Base delay: 2 seconds
    "cap_sec": 60            # Max delay: 60 seconds
}

# Exponential: 2s, 4s, 8s, 16s, 32s, 60s (capped)
# Fixed: 2s, 2s, 2s, 2s, ...
```

---

## Tips & Troubleshooting

**Check Docker is running:**
```bash
docker ps
# or for Podman:
podman ps
```

**Use Podman instead of Docker:**
```bash
xnat-pipelines run --engine podman ...
```

**View full logs:**
```bash
cat ./my_runs/run_*/run.log
```

**Test without execution:**
```bash
xnat-pipelines run --dry-run ...
```

**Monitor jobs in real-time:**
```bash
xnat-pipelines-dashboard --runs ./my_runs --port 8080
```

**Cancel a running job:**
```python
job = executor.run(...)
# Later:
job.cancel()
```

---

## Real-World Workflow Example

Complete workflow for processing multiple XNAT experiments:

```python
import xnat
from xnat_pipelines.executor import Executor
from xnat_pipelines.batch import BatchRunner

# 1. Connect to XNAT
with xnat.connect("https://xnat.example.org", token="token") as xn:
    
    # 2. Find experiments to process
    project = xn.projects["MyProject"]
    contexts = [
        {"level": "experiment", "id": exp.id}
        for exp in project.experiments.values()
        if "T1" in exp.label  # Filter for T1 scans
    ]
    
    print(f"Found {len(contexts)} T1 experiments to process")
    
    # 3. Setup batch processing
    executor = Executor(mode="auto")
    batch = BatchRunner(executor, concurrency=8, retry={"max_retries": 2})
    
    # 4. Run dcm2niix on all
    results = batch.run_many(
        xnat_session=xn,
        command_ref="dcm2niix:latest",
        contexts=contexts,
        inputs={"compress": "y", "bids_sidecar": "y"},
        io={
            "download": True, 
            "upload": True,
            "resource_filters": {"resource_names": ["DICOM"]}
        }
    )
    
    # 5. Report results
    print(batch.summary(results))
    
    failed = [r for r in results if r.status.lower() == "failed"]
    if failed:
        print(f"\n⚠️  Failed jobs: {len(failed)}")
        for f in failed:
            print(f"  - {f.context['id']}: {f.error}")
```
