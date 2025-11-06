#!/usr/bin/env bash
set -euo pipefail

# Example 1 from EXAMPLE_USAGE.md:
# Run the debug container locally in dry-run mode so Docker is not required.

CLI=(xnat-pipelines)
if ! command -v "${CLI[0]}" >/dev/null 2>&1; then
  CLI=(python -m xnat_pipelines.cli)
fi

RUN_ROOT=${1:-demo_runs}
WORKDIR="${RUN_ROOT%/}/example1_single"
mkdir -p "$WORKDIR"

echo "Writing dry-run manifest under $WORKDIR"
"${CLI[@]}" run \
  --mode local \
  --command ghcr.io/xnat/debug-command:latest \
  --level experiment \
  --id XNAT_E00123 \
  --inputs '{"message":"Hello XNAT","sleep":2,"should_fail":false}' \
  --workdir "$WORKDIR" \
  --dry-run

echo
echo "Dry-run complete. Inspect $(ls -1 "$WORKDIR") for run.json and run.log."
