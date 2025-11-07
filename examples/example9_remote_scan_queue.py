#!/usr/bin/env python3
"""
Example 7c: Queue-driven remote scan processing for an entire project.

Builds the scan inventory (like Example 7), then hands those contexts to
BatchRunner.run_queue to keep a fixed number of remote jobs in flight while
polling for status updates.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import xnat

from xnat_pipelines.batch import BatchRunner, QueueEvent
from xnat_pipelines.executor import Executor


@dataclass
class ScanTarget:
    experiment_id: str
    scan_id: str
    label: Optional[str]
    archive_path: str


def requests_session(user: Optional[str], password: Optional[str], token: Optional[str]) -> requests.Session:
    sess = requests.Session()
    if token:
        sess.headers["Authorization"] = f"Bearer {token}"
    elif user and password:
        sess.auth = (user, password)
    return sess


def fetch_scan_targets(base_url: str, project: str, session: requests.Session) -> List[ScanTarget]:
    resp = session.get(f"{base_url}/data/projects/{project}/experiments", params={"format": "json"})
    resp.raise_for_status()
    experiments = resp.json()["ResultSet"]["Result"]

    targets: List[ScanTarget] = []
    for exp in experiments:
        exp_id = exp["ID"]
        scans_resp = session.get(f"{base_url}/data/experiments/{exp_id}/scans", params={"format": "json"})
        scans_resp.raise_for_status()
        scans = scans_resp.json()["ResultSet"]["Result"]

        for scan in scans:
            scan_uri = scan["URI"]
            res_resp = session.get(f"{base_url}{scan_uri}/resources", params={"format": "json"})
            res_resp.raise_for_status()
            resources = res_resp.json()["ResultSet"]["Result"]
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue-based remote scan runner.")
    parser.add_argument("--base-url", default="http://demo02.xnatworks.io")
    parser.add_argument("--project", default="Prostate-AEC")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--token", help="XNAT auth token (overrides user/password).")
    parser.add_argument("--command", default="dcm2niix", help="Container command/ID to run.")
    parser.add_argument("--bids", default="y", choices=["y", "n"])
    parser.add_argument("--other-options", default="")
    parser.add_argument("--limit", type=int, help="Limit number of scans processed.")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--job-timeout", type=int, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sess = requests_session(args.user, args.password, args.token)

    print(f"Discovering scans in project {args.project}...")
    targets = fetch_scan_targets(args.base_url, args.project, sess)
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        print("No qualifying scans found.")
        return
    print(f"Queued {len(targets)} scan contexts.")

    contexts: List[Dict[str, str]] = [
        {
            "level": "scan",
            "id": target.archive_path,
            "experiment_id": target.experiment_id,
            "scan_id": target.scan_id,
            "label": target.label or "",
        }
        for target in targets
    ]

    executor = Executor(mode="remote")
    runner = BatchRunner(executor=executor, concurrency=args.concurrency)

    connect_kwargs = {}
    if args.token:
        connect_kwargs["token"] = args.token
    else:
        connect_kwargs["user"] = args.user
        connect_kwargs["password"] = args.password

    def inputs_factory(ctx: Dict[str, str], _index: int) -> Dict[str, str]:
        payload = {"bids": args.bids}
        if args.other_options:
            payload["other-options"] = args.other_options
        return payload

    def logger(event: QueueEvent) -> None:
        label = event.context.get("scan_id") or event.context.get("id", "?")
        prefix = f"[{event.index}/{len(contexts)}]"
        if event.event == "submitted":
            print(
                f"{prefix} queued {event.context.get('experiment_id')} scan {label} "
                f"(job_id={event.job_id})"
            )
        elif event.event == "status":
            print(f"[poll] scan {label} status={event.status}")
        elif event.event == "complete":
            duration = f" ({event.duration_sec:.1f}s)" if event.duration_sec is not None else ""
            extra = f" error={event.error}" if event.error else ""
            print(
                f"{prefix} done {event.context.get('experiment_id')} scan {label} "
                f"-> {event.status}{duration}{extra}"
            )
        elif event.event == "error":
            print(f"{prefix} error scan {label}: {event.status}")

    try:
        with xnat.connect(args.base_url, **connect_kwargs) as xn:
            results = runner.run_queue(
                xnat_session=xn,
                command_ref=args.command,
                contexts=contexts,
                inputs={},
                poll_interval=args.poll_interval,
                job_timeout=args.job_timeout,
                status_callback=logger,
                inputs_factory=inputs_factory,
            )
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)

    print("\nSummary")
    print(runner.summary(results))
    failed = [r for r in results if r.error]
    if failed:
        print("\nFailures:")
        for res in failed:
            print(f"  {res.context.get('scan_id', res.context.get('id'))}: {res.error}")


if __name__ == "__main__":
    main()
