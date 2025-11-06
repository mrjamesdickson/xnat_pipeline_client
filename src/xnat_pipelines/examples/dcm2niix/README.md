# Example: xnat/dcm2niix

Use **dcm2niix** to convert `/input` DICOM to `/output` NIfTI with schema-aware mapping.

## Register in XNAT (remote)
- **Name**: `xnat/dcm2niix`
- **Version**: `latest`
- **Image**: `ghcr.io/xnat/dcm2niix:latest` (update to your preferred image, e.g., `docker.io/rordenlab/dcm2niix:latest`)
- **Mounts**: input=`/input`, output=`/output`
- **Inputs** (example; adjust to the flags your image supports):
  - `compress` (`-z`, default `y`)
  - `bids_sidecar` (`-b`, default `y`)
  - `filename` (`-f`, default `%p_%s`)
  - `merge_nifti` (`-m`, default `4`)
  - `text_notes` (`-x`, default `""`)

> If your dcm2niix build uses different flags or defaults, modify `examples/dcm2niix/command.json`.
> The **xnat_pipelines** local backend will read these mappings and build the container invocation accordingly.

## Run via CLI (auto mode)
```bash
xnat-pipelines run --mode auto   --url https://xnat.example.org --token $TOKEN   --command xnat/dcm2niix   --level experiment --id XNAT_E_MRI_001   --inputs '{"compress":"y","bids_sidecar":"y","filename":"%p_%s","merge_nifti":4}'
```

## Local-only
```bash
xnat-pipelines run --mode local   --command docker.io/rordenlab/dcm2niix:latest   --level experiment --id XNAT_E_MRI_001   --inputs '{"compress":"y","bids_sidecar":"y","filename":"%p_%s"}'
```

## Batch
```bash
xnat-pipelines batch --mode auto   --url https://xnat.example.org --token $TOKEN   --command xnat/dcm2niix   --contexts @contexts.json   --io '{"download":true,"upload":true,"resource_name":"NIfTI"}'   --concurrency 4
```
