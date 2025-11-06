from __future__ import annotations
import argparse, json, sys
from typing import List
import xnat
from xnat import exceptions

from .executor import Executor
from .containers import ContainerClient
from .batch import BatchRunner

CONTEXT_TO_LEVEL = {
    "project": "project",
    "subject": "subject",
    "session": "experiment",
    "experiment": "experiment",
    "scan": "scan",
    "assessor": "assessor",
    "resource": "resource",
}
def _connect_kwargs(args):
    kwargs = {}
    if getattr(args, "user", None):
        kwargs["user"] = args.user
    if getattr(args, "password", None):
        kwargs["password"] = args.password
    if getattr(args, "token", None):
        kwargs["token"] = args.token
    return kwargs


def _connect_or_exit(url, kwargs):
    try:
        return xnat.connect(url, **kwargs)
    except exceptions.XNATAuthError as exc:
        print(f"Authentication failed for {url}: {exc}", file=sys.stderr)
        print("Provide --user/--password or --token.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="xnat-pipelines")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list-commands", help="List container commands from XNAT")
    ls.add_argument("--url", required=True)
    ls.add_argument("--user")
    ls.add_argument("--password")
    ls.add_argument("--token")
    ls.add_argument("--routes", help="JSON of route overrides")

    lrun = sub.add_parser("list-running", help="List recent container jobs from XNAT")
    lrun.add_argument("--url", required=True)
    lrun.add_argument("--user")
    lrun.add_argument("--password")
    lrun.add_argument("--token")
    lrun.add_argument("--routes", help="JSON of route overrides")
    lrun.add_argument("--limit", type=int, default=20, help="Number of recent jobs to fetch")

    sample = sub.add_parser("sample-from-id", help="Print a Python snippet to rerun a container job by ID")
    sample.add_argument("container_id")
    sample.add_argument("--url", required=True)
    sample.add_argument("--user")
    sample.add_argument("--password")
    sample.add_argument("--token")
    sample.add_argument("--routes", help="JSON of route overrides")

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
        connect_kwargs = _connect_kwargs(args)
        with _connect_or_exit(args.url, connect_kwargs) as xn:
            cc = ContainerClient.from_xnat(xn, routes=routes)
            for c in cc.list_commands():
                print(f"{c.id}\t{c.name}\t{c.version}\t{c.image}")
        return

    if args.cmd == "list-running":
        connect_kwargs = _connect_kwargs(args)
        with _connect_or_exit(args.url, connect_kwargs) as xn:
            cc = ContainerClient.from_xnat(xn, routes=routes)
            rows = cc.list_running(size=args.limit)
            for row in rows:
                cid = row.get("id")
                command = row.get("command-name") or row.get("command-id")
                status = row.get("status")
                wrapper = row.get("wrapper-id")
                context_param = None
                context_value = None
                for entry in (row.get("inputs") or []):
                    if entry.get("name") == "context":
                        context_param = entry.get("value")
                        break
                if context_param:
                    for entry in (row.get("inputs") or []):
                        if entry.get("name") == context_param:
                            context_value = entry.get("value")
                            break
                if isinstance(context_value, str) and context_value.startswith("/archive/"):
                    context_value = context_value.split("/")[-1]
                context_display = f"{context_param}={context_value}" if context_param else "context=?"
                print(f"{cid}\t{command}\t{status}\t{context_display}\twrapper={wrapper}")
        return

    if args.cmd == "sample-from-id":
        connect_kwargs = _connect_kwargs(args)
        with _connect_or_exit(args.url, connect_kwargs) as xn:
            cc = ContainerClient.from_xnat(xn, routes=routes)
            detail = cc.get_container(args.container_id)
            commands = cc.list_commands()

        command_id = detail.get("command-id") or detail.get("commandId")
        command_name = detail.get("command-name") or detail.get("commandName")
        command_ref = command_name or command_id
        wrapper_id = detail.get("wrapper-id") or detail.get("wrapperId")

        wrapper_contexts: List[str] = []
        for cmd in commands:
            if str(command_id) == str(cmd.id) or cmd.name == command_name:
                wrappers = cmd.raw.get("xnat") or []
                for wrapper in wrappers:
                    if str(wrapper.get("id")) == str(wrapper_id):
                        wrapper_contexts = wrapper.get("contexts") or []
                        break
                break

        inputs = detail.get("inputs") or []
        context_param = None
        target_value = None
        for entry in inputs:
            if entry.get("name") == "context":
                context_param = entry.get("value")
                break
        if context_param:
            for entry in inputs:
                if entry.get("name") == context_param:
                    target_value = entry.get("value")
                    break

        if wrapper_contexts and not context_param:
            first_ctx = wrapper_contexts[0]
            if isinstance(first_ctx, str) and ":" in first_ctx:
                context_param = first_ctx.split(":", 1)[1]
        if isinstance(context_param, str) and ":" in context_param:
            context_param = context_param.split(":", 1)[1]

        level = CONTEXT_TO_LEVEL.get(str(context_param), "experiment")
        if not target_value:
            target_value = "XNAT_E00001"

        wrapper_comment = ""
        if wrapper_contexts:
            readable_contexts = ", ".join(wrapper_contexts)
            wrapper_comment = f"# wrapper contexts: {readable_contexts}"

        input_hints = {}
        for entry in inputs:
            name = entry.get("name")
            if isinstance(name, str) and name.startswith("inputs."):
                key = name[len("inputs.") :]
                input_hints[key] = entry.get("value") or ""

        input_lines: List[str] = []
        for key, value in input_hints.items():
            display = value if value else "<fill in>"
            if isinstance(display, str):
                display = display.replace('"', '\\"')
            input_lines.append(f'        "{key}": "{display}"')
        if not input_lines:
            input_lines.append('        "command": "echo hello world"')

        connect_args: List[str] = [f'"{args.url}"']
        if getattr(args, "user", None):
            connect_args.append(f'user="{args.user}"')
        else:
            connect_args.append('user="<user>"')
        if getattr(args, "password", None):
            connect_args.append(f'password="{args.password}"')
        else:
            connect_args.append('password="<password>"')
        if getattr(args, "token", None):
            connect_args.append(f'token="{args.token}"')
        connect_call = ", ".join(connect_args)

        snippet_lines = [
            "from xnat_pipelines.executor import Executor",
            "import xnat",
            "",
            f"# container id {args.container_id}, command {command_ref}",
        ]
        if wrapper_comment:
            snippet_lines.append(wrapper_comment)
        snippet_lines.extend([
            f"with xnat.connect({connect_call}) as xn:",
            "    executor = Executor(mode=\"remote\")",
            "    job = executor.run(",
            "        xnat_session=xn,",
            f"        command_ref=\"{command_ref}\",",
            f"        context={{\"level\": \"{level}\", \"id\": \"{target_value}\"}},",
            "        inputs={",
        ])
        snippet_lines.extend(input_lines)
        snippet_lines.extend(
            [
                "        },",
                "    )",
                "    job.wait()",
                "    print(job.status)",
            ]
        )

        print("\n".join(snippet_lines))
        return

    if args.cmd in ("run","batch"):
        connect_kwargs = _connect_kwargs(args)
        xn = None
        if args.mode in ("auto","remote"):
            if not args.url:
                print("error: --url required for remote/auto modes", file=sys.stderr)
                sys.exit(2)
            xn = _connect_or_exit(args.url, connect_kwargs)

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
