
# xnat_pipelines (v0.5.0)

**New in 0.5.0**
- **Schema-aware input mapping** for local runs: we read the XNAT command JSON (when resolving via XNAT)
  and translate `inputs` → env vars/args and `mounts` → container volume bindings. This improves **parity**
  between remote and local execution.
- **Lightweight HTML dashboard** for batch monitoring. No external deps. Launch with:
  ```bash
  xnat-pipelines-dashboard --runs ./xnat_local_runs --port 8080
  ```

### Schema-aware mapping overview
- We examine `cmd.raw` for common Container Service fields:
  - `inputs`: list/dict of inputs (`{name, type, default, env, arg}`)
  - `mounts`: input/output mount points (e.g., `{"input":"/input","output":"/output"}`)
- Local mode now honors these, building `docker run` flags accordingly.

### Dashboard
- Serves a static page with JS that scans your `--runs` directory, reading `run.json` and `run.log` from each run.
- Exposes a simple `/status.json` endpoint with job states, sizes, and recent log tail.

See `examples/dual_mode_execution_demo.ipynb` (from v0.2.0), `examples/batch_demo.ipynb` (v0.3.0). Dashboard scripts live in `examples/` and `xnat_pipelines.dashboard` entrypoint.
