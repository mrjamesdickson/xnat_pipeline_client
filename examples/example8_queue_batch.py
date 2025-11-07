#!/usr/bin/env python3
"""
Example 8: Queue-driven batch orchestration with live status polling.

Demonstrates how to:
  * Feed contexts from a queue (generated IDs in this demo).
  * Cap concurrency explicitly.
  * Poll each job handle for status changes until completion.

Defaults to local dry-run mode so you can explore the flow without Docker or XNAT.
Pass --execute to run the referenced container command, or --mode auto/remote with
--url/--token to hit a live XNAT.
"""

from __future__ import annotations

import argparse
from typing import Dict, List

import xnat

from xnat_pipelines.batch import BatchRunner, QueueEvent
from xnat_pipelines.executor import Executor


def build_contexts(level: str, prefix: str, count: int, start_index: int) -> List[Dict[str, str]]:
    return [{"level": level, "id": f"{prefix}{start_index + i}"} for i in range(count)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local queue demo with live polling.")
    parser.add_argument("--mode", choices=["local", "remote", "auto"], default="local")
    parser.add_argument("--url")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--token")
    parser.add_argument("--command", default="ghcr.io/xnat/debug-command:latest")
    parser.add_argument("--contexts", type=int, default=6, help="Number of synthetic contexts to enqueue.")
    parser.add_argument("--level", choices=["project", "subject", "experiment", "scan"], default="experiment")
    parser.add_argument("--context-prefix", default="XNAT_E", help="Prefix used for generated IDs.")
    parser.add_argument("--start-index", type=int, default=100, help="Starting numeric suffix for IDs.")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--sleep-sec", type=int, default=3, help="Input passed to the debug command.")
    parser.add_argument("--message-template", default="Hello from {context_id} (#{position})")
    parser.add_argument("--workdir", default="xnat_local_runs/example8")
    parser.add_argument("--engine", default="docker", choices=["docker", "podman"])
    parser.add_argument("--execute", dest="dry_run", action="store_false", help="Run the actual container instead of dry-run.")
    parser.set_defaults(dry_run=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contexts = build_contexts(args.level, args.context_prefix, args.contexts, args.start_index)

    executor = Executor(mode=args.mode)
    runner = BatchRunner(executor=executor, concurrency=args.concurrency)

    xn = None
    if args.mode in ("remote", "auto"):
        if not args.url:
            raise SystemExit("--url required for remote/auto modes")
        connect_kwargs = {}
        if args.user:
            connect_kwargs["user"] = args.user
        if args.password:
            connect_kwargs["password"] = args.password
        if args.token:
            connect_kwargs["token"] = args.token
        xn = xnat.connect(args.url, **connect_kwargs)

    def inputs_factory(ctx: Dict[str, str], index: int) -> Dict[str, str]:
        return {
            "message": args.message_template.format(context_id=ctx["id"], position=index, level=ctx["level"]),
            "sleep": str(args.sleep_sec),
            "should_fail": "false",
        }

    def logger(event: QueueEvent) -> None:
        label = event.context.get("id", "?")
        prefix = f"[{event.index}/{len(contexts)}]"
        if event.event == "submitted":
            print(f"{prefix} queued {label} (job_id={event.job_id})")
        elif event.event == "status":
            print(f"[poll] {label} status={event.status}")
        elif event.event == "complete":
            duration = f" ({event.duration_sec:.1f}s)" if event.duration_sec is not None else ""
            extra = f" error={event.error}" if event.error else ""
            print(f"{prefix} done {label} -> {event.status}{duration}{extra}")
        elif event.event == "error":
            print(f"{prefix} error {label}: {event.status}")

    try:
        results = runner.run_queue(
            xnat_session=xn,
            command_ref=args.command,
            contexts=contexts,
            inputs={},
            workdir=args.workdir,
            engine=args.engine,
            dry_run=args.dry_run,
            poll_interval=args.poll_interval,
            status_callback=logger,
            inputs_factory=inputs_factory,
        )
    finally:
        if xn:
            xn.disconnect()

    print("\nSummary")
    print(runner.summary(results))
    for res in results:
        duration = f"{res.duration_sec:.1f}s" if res.duration_sec is not None else "n/a"
        print(f"  {res.context['id']} -> {res.status} ({duration}) {res.error or ''}")


if __name__ == "__main__":
    main()
