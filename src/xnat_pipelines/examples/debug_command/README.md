# Example: xnat/debug-command

A minimal command for testing the Container Service and the **xnat_pipelines** companion.

## Register in XNAT (remote)
- **Name**: `xnat/debug-command`
- **Version**: `latest`
- **Image**: `ghcr.io/xnat/debug-command:latest` (update if your registry/tag differs)
- **Mounts**: input=`/input`, output=`/output`
- **Inputs**:
  - `message` (arg: `--message`, default: `hello`)
  - `sleep` (arg: `--sleep`, default: `0`)
  - `should_fail` (env: `SHOULD_FAIL`, default: `false`)

## Run via CLI (auto mode)
```bash
xnat-pipelines run --mode auto   --url https://xnat.example.org --token $TOKEN   --command xnat/debug-command   --level experiment --id XNAT_E12345   --inputs '{"message":"hi","sleep":1,"should_fail":false}'
```

## Local-only
```bash
xnat-pipelines run --mode local   --command ghcr.io/xnat/debug-command:latest   --level experiment --id XNAT_E12345   --inputs '{"message":"local","sleep":0}'
```

## Batch
```bash
xnat-pipelines batch --mode auto   --url https://xnat.example.org --token $TOKEN   --command xnat/debug-command   --contexts @contexts.json   --concurrency 4
```
