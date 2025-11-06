from __future__ import annotations
import argparse, json, sys
import xnat

from .executor import Executor
from .containers import ContainerClient
from .batch import BatchRunner

def main():
    parser = argparse.ArgumentParser(prog="xnat-pipelines")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list-commands", help="List container commands from XNAT")
    ls.add_argument("--url", required=True)
    ls.add_argument("--user")
    ls.add_argument("--password")
    ls.add_argument("--token")
    ls.add_argument("--routes", help="JSON of route overrides")

    run = sub.add_parser("run", help="Run a container command (remote/local/auto)")
    run.add_argument("--mode", default="auto", choices=["auto", "remote", "local"])
    run.add_argument("--url")
    run.add_argument("--user")
    run.add_argument("--password")
    run.add_argument("--token")
    run.add_argument("--routes")
    run.add_argument("--command", required=True)
    run.add_argument("--level", required=True, choices=["project","subject","experiment","scan","resource"])
    run.add_argument("--id", required=True)
    run.add_argument("--inputs", default="{}")
    run.add_argument("--io", default="{}")
    run.add_argument("--retry", default="{}")
    run.add_argument("--workdir", default=None)
    run.add_argument("--engine", default="docker", choices=["docker","podman"])
    run.add_argument("--dry-run", action="store_true")

    batch = sub.add_parser("batch", help="Batch run across many contexts")
    batch.add_argument("--mode", default="auto", choices=["auto", "remote", "local"])
    batch.add_argument("--url")
    batch.add_argument("--user")
    batch.add_argument("--password")
    batch.add_argument("--token")
    batch.add_argument("--routes")
    batch.add_argument("--command", required=True)
    batch.add_argument("--contexts", required=True, help="JSON list of contexts")
    batch.add_argument("--inputs", default="{}")
    batch.add_argument("--io", default="{}")
    batch.add_argument("--retry", default="{}")
    batch.add_argument("--concurrency", type=int, default=4)
    batch.add_argument("--workdir", default=None)
    batch.add_argument("--engine", default="docker", choices=["docker","podman"])
    batch.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    routes = json.loads(args.routes) if args.routes else None

    if args.cmd == "list-commands":
        connect_kwargs = {}
        if args.user:
            connect_kwargs["user"] = args.user
        if args.password:
            connect_kwargs["password"] = args.password
        if args.token:
            connect_kwargs["token"] = args.token
        with xnat.connect(args.url, **connect_kwargs) as xn:
            cc = ContainerClient.from_xnat(xn, routes=routes)
            for c in cc.list_commands():
                print(f"{c.id}\t{c.name}\t{c.version}\t{c.image}")
        return

    if args.cmd in ("run","batch"):
        xn = None
        if args.mode in ("auto","remote"):
            if not args.url:
                print("error: --url required for remote/auto modes", file=sys.stderr)
                sys.exit(2)
            connect_kwargs = {}
            if args.user:
                connect_kwargs["user"] = args.user
            if args.password:
                connect_kwargs["password"] = args.password
            if args.token:
                connect_kwargs["token"] = args.token
            xn = xnat.connect(args.url, **connect_kwargs)

        exec = Executor(mode=args.mode)

        try:
            if args.cmd == "run":
                job = exec.run(
                    xnat_session=xn,
                    command_ref=args.command,
                    context={"level": args.level, "id": args.id},
                    inputs=json.loads(args.inputs),
                    routes=routes,
                    io=json.loads(args.io),
                    retry=json.loads(args.retry),
                    workdir=args.workdir,
                    engine=args.engine,
                    dry_run=args.dry_run,
                )
                job.wait()
                print(job.status)
                print(job.stdout_tail())
            else:
                contexts = json.loads(args.contexts)
                runner = BatchRunner(executor=exec, concurrency=args.concurrency, retry=json.loads(args.retry))
                results = runner.run_many(
                    xnat_session=xn,
                    command_ref=args.command,
                    contexts=contexts,
                    inputs=json.loads(args.inputs),
                    routes=routes,
                    io=json.loads(args.io),
                    workdir=args.workdir,
                    engine=args.engine,
                    dry_run=args.dry_run,
                )
                print(runner.summary(results))
                for r in results:
                    print(f"{r.context} -> {r.status} ({r.backend}) {r.error or ''}")
        finally:
            if xn is not None:
                xn.disconnect()

if __name__ == "__main__":
    main()
