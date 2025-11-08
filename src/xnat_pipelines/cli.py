from __future__ import annotations
import argparse, json, sys
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import netrc
import os
import xnat
from xnat import exceptions

from . import __version__ as PKG_VERSION
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

CONTEXT_NAME_ALIASES = {
    "projectdata": "project",
    "subjectdata": "subject",
    "experimentdata": "experiment",
    "imagesessiondata": "session",
    "sessiondata": "session",
    "imagescandata": "scan",
    "scancontext": "scan",
    "imageassessordata": "assessor",
    "assessordata": "assessor",
    "imageresourcedata": "resource",
    "resourcecatalog": "resource",
}

DEFAULT_CONTEXT_IDS = {
    "project": "XNAT_P00001",
    "subject": "XNAT_S00001",
    "experiment": "XNAT_E00001",
    "scan": "/archive/experiments/XNAT_E00001/scans/1",
    "assessor": "XNAT_A00001",
    "resource": "/archive/resources/RESOURCE_LABEL",
}


def _normalize_context_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    token = str(value).strip()
    if ":" in token:
        token = token.split(":", 1)[1]
    if token in CONTEXT_TO_LEVEL:
        return token
    lowered = token.lower()
    if lowered in CONTEXT_TO_LEVEL:
        return lowered
    normalized = token.replace("-", "").replace("_", "").lower()
    alias = CONTEXT_NAME_ALIASES.get(normalized)
    if alias:
        return alias
    return token

def _netrc_credentials(url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not url:
        return (None, None)
    hostname = urlparse(url).hostname
    if not hostname:
        return (None, None)
    netrc_path = os.environ.get("NETRC") or os.path.expanduser("~/.netrc")
    if not os.path.exists(netrc_path):
        return (None, None)
    try:
        auth = netrc.netrc(netrc_path).authenticators(hostname)
    except (netrc.NetrcParseError, FileNotFoundError):
        return (None, None)
    if not auth:
        return (None, None)
    login, _, password = auth
    return (login, password)


def _connect_kwargs(args):
    kwargs = {}
    if getattr(args, "user", None):
        kwargs["user"] = args.user
    if getattr(args, "password", None):
        kwargs["password"] = args.password
    if getattr(args, "token", None):
        kwargs["token"] = args.token
    if "user" not in kwargs and "token" not in kwargs:
        url = getattr(args, "url", None)
        login, password = _netrc_credentials(url)
        if login:
            kwargs["user"] = login
        if password and "password" not in kwargs:
            kwargs["password"] = password
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PKG_VERSION}",
        help="Show the installed xnat-pipelines version and exit",
    )
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
    batch.add_argument("--queue-mode", action="store_true", help="Process contexts via a managed queue with live polling.")
    batch.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between queue status polls.")
    batch.add_argument("--job-timeout", type=int, default=3600, help="Timeout (s) when waiting for queued jobs to finalize.")

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
        target_value = None
        raw_context_param = None
        for entry in inputs:
            if entry.get("name") == "context":
                raw_context_param = entry.get("value")
                break
        context_param = _normalize_context_name(raw_context_param)
        if context_param:
            for entry in inputs:
                if entry.get("name") == context_param:
                    target_value = entry.get("value")
                    break

        if not context_param and wrapper_contexts:
            first_ctx = next((ctx for ctx in wrapper_contexts if isinstance(ctx, str)), None)
            context_param = _normalize_context_name(first_ctx)

        level = CONTEXT_TO_LEVEL.get(context_param, "experiment")
        if not target_value:
            target_value = DEFAULT_CONTEXT_IDS.get(level, "XNAT_E00001")

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
        connect_args.append(f'user="{getattr(args, "user", "<user>") or "<user>"}"')
        password_supplied = getattr(args, "password", None) is not None
        token_supplied = getattr(args, "token", None) is not None
        if password_supplied or not token_supplied:
            connect_args.append('password="<password>"')
        if token_supplied:
            connect_args.append('token="<token>"')
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
                if not isinstance(contexts, list):
                    print("error: --contexts must be a JSON list of context dictionaries", file=sys.stderr)
                    sys.exit(2)
                retry_cfg = json.loads(args.retry)
                runner = BatchRunner(executor=exec, concurrency=args.concurrency, retry=retry_cfg)
                inputs_cfg = json.loads(args.inputs)
                io_cfg = json.loads(args.io)
                if args.queue_mode:
                    total_contexts = len(contexts)

                    def _queue_logger(event):
                        label = event.context.get("id", "?")
                        prefix = f"[{event.index}/{total_contexts}]" if total_contexts else f"[{event.index}]"
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

                    results = runner.run_queue(
                        xnat_session=xn,
                        command_ref=args.command,
                        contexts=contexts,
                        inputs=inputs_cfg,
                        routes=routes,
                        io=io_cfg,
                        workdir=args.workdir,
                        engine=args.engine,
                        dry_run=args.dry_run,
                        poll_interval=args.poll_interval,
                        job_timeout=args.job_timeout,
                        status_callback=_queue_logger,
                    )
                else:
                    results = runner.run_many(
                        xnat_session=xn,
                        command_ref=args.command,
                        contexts=contexts,
                        inputs=inputs_cfg,
                        routes=routes,
                        io=io_cfg,
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
