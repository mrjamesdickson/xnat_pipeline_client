#!/usr/bin/env python3
"""
Example 7: Launch dcm2niix remotely for every DICOM-backed scan in a project.

This demonstrates how to enumerate scans, filter on the presence of a DICOM
resource, and drive the XNAT Container Service through xnat_pipelines'
remote executor. It mirrors the JavaScript workflow in xnat_proxy_site.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import requests
import xnat

from xnat_pipelines.executor import Executor


@dataclass
class ScanTarget:
    experiment_id: str
    scan_id: str
    label: Optional[str]
    archive_path: str


def fetch_scans_with_dicoms(
    base_url: str,
    project: str,
    session: requests.Session,
) -> List[ScanTarget]:
    experiments_resp = session.get(
        f"{base_url}/data/projects/{project}/experiments",
        params={"format": "json"},
    )
    experiments_resp.raise_for_status()
    experiments = experiments_resp.json()["ResultSet"]["Result"]

    targets: List[ScanTarget] = []
    for exp in experiments:
        exp_id = exp["ID"]
        scans_resp = session.get(
            f"{base_url}/data/experiments/{exp_id}/scans",
            params={"format": "json"},
        )
        scans_resp.raise_for_status()
        scans = scans_resp.json()["ResultSet"]["Result"]

        for scan in scans:
            scan_uri = scan["URI"]  # /data/experiments/<ID>/scans/<scanID>
            resources_resp = session.get(
                f"{base_url}{scan_uri}/resources",
                params={"format": "json"},
            )
            resources_resp.raise_for_status()
            resources = resources_resp.json()["ResultSet"]["Result"]

            has_dicom = any(res.get("label") == "DICOM" for res in resources)
            if not has_dicom:
                continue

            archive_path = scan_uri.replace("/data/", "/archive/", 1)
            targets.append(
                ScanTarget(
                    experiment_id=exp_id,
                    scan_id=scan["ID"],
                    label=scan.get("series_description") or scan.get("type"),
                    archive_path=archive_path,
                )
            )
    return targets


def run_remote_dcm2niix(
    base_url: str,
    user: str,
    password: str,
    project: str,
    bids_sidecar: str,
    other_options: str,
    limit: Optional[int],
) -> Dict[str, int]:
    session = requests.Session()
    session.auth = (user, password)

    print(f"Discovering scans in project {project}...")
    targets = fetch_scans_with_dicoms(base_url, project, session)
    if limit is not None:
        targets = targets[:limit]
    print(f"Found {len(targets)} scans with DICOM resources.")

    if not targets:
        return {"total": 0, "complete": 0, "failed": 0}

    executor = Executor(mode="remote")
    summary = {"total": len(targets), "complete": 0, "failed": 0}

    with xnat.connect(base_url, user=user, password=password) as xn:
        for idx, target in enumerate(targets, start=1):
            context = {"level": "scan", "id": target.archive_path}
            inputs = {"bids": bids_sidecar}
            if other_options:
                inputs["other-options"] = other_options

            try:
                job = executor.run(
                    xnat_session=xn,
                    command_ref="dcm2niix",
                    context=context,
                    inputs=inputs,
                )
                job.wait(timeout=600)
                status = job.status
                print(
                    f"[{idx}/{summary['total']}] {target.experiment_id} scan {target.scan_id}"
                    f" ({target.label or 'no label'}): {status}"
                )
                if status.lower().startswith("complete"):
                    summary["complete"] += 1
                else:
                    summary["failed"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["failed"] += 1
                print(
                    f"[{idx}/{summary['total']}] {target.experiment_id} scan {target.scan_id} ERROR: {exc}"
                )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote dcm2niix batch launcher.")
    parser.add_argument("--base-url", default="http://demo02.xnatworks.io")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--project", default="Prostate-AEC")
    parser.add_argument("--bids", default="y", choices=["y", "n"], help="Value for the dcm2niix -b flag.")
    parser.add_argument("--other-options", default="", help="Additional flags to append to the dcm2niix command.")
    parser.add_argument("--limit", type=int, help="Limit the number of scans processed.")
    args = parser.parse_args()

    summary = run_remote_dcm2niix(
        base_url=args.base_url,
        user=args.user,
        password=args.password,
        project=args.project,
        bids_sidecar=args.bids,
        other_options=args.other_options,
        limit=args.limit,
    )

    print("\nSummary:", summary)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)
