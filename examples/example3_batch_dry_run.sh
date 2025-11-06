#!/usr/bin/env bash
set -euo pipefail

# Example 3 from EXAMPLE_USAGE.md:
# Batch three experiments with the debug container. Uses dry-run to avoid Docker.

CLI=(xnat-pipelines)
if ! command -v "${CLI[0]}" >/dev/null 2>&1; then
  CLI=(python -m xnat_pipelines.cli)
fi

RUN_ROOT=${1:-demo_runs}
WORKDIR="${RUN_ROOT%/}/example3_batch"
mkdir -p "$WORKDIR"

CONTEXTS='[
  {"level":"experiment","id":"XNAT_E001"},
  {"level":"experiment","id":"XNAT_E002"},
  {"level":"experiment","id":"XNAT_E003"}
]'

echo "Launching dry-run batch manifest under $WORKDIR"
"${CLI[@]}" batch \
  --mode local \
  --command ghcr.io/xnat/debug-command:latest \
  --contexts "$CONTEXTS" \
  --inputs '{"message":"Batch processing","sleep":1}' \
  --io '{"download":false,"upload":false}' \
  --workdir "$WORKDIR" \
  --concurrency 3 \
  --dry-run

cat <<'MSG'

Dry-run complete.
- Summary printed above shows each context prepared.
- Remove --dry-run once Docker/Podman is available to execute the batch.
MSG
