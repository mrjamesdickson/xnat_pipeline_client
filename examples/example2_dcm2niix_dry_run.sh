#!/usr/bin/env bash
set -euo pipefail

# Example 2 from EXAMPLE_USAGE.md:
# Prepare a local dcm2niix run. Starts in dry-run mode so you can preview the docker command.

CLI=(xnat-pipelines)
if ! command -v "${CLI[0]}" >/dev/null 2>&1; then
  CLI=(python -m xnat_pipelines.cli)
fi

RUN_ROOT=${1:-demo_runs}
WORKDIR="${RUN_ROOT%/}/example2_dcm2niix"
mkdir -p "$WORKDIR"

echo "Preparing dcm2niix dry-run manifest under $WORKDIR"
"${CLI[@]}" run \
  --mode local \
  --command ghcr.io/xnat/dcm2niix:latest \
  --level experiment \
  --id XNAT_E00456 \
  --inputs '{"compress":"y","bids_sidecar":"y","filename":"%p_%s"}' \
  --workdir "$WORKDIR" \
  --dry-run

cat <<'MSG'

Dry-run complete.
- Inspect run.json for the generated docker/podman command.
- Remove --dry-run (and ensure Docker/Podman is running) to execute the conversion.
MSG
