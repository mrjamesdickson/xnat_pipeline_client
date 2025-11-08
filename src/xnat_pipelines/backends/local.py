from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, TYPE_CHECKING
import os, subprocess, shlex, time, pathlib, json

from ..containers import ContainerClient
from ..io_utils import ensure_dirs, stage_from_xnat, upload_outputs_to_xnat
from ..schema_mapping import map_inputs_and_mounts, resolve_mounts

if TYPE_CHECKING:
    from ..executor import JobHandle

@dataclass
class _LocalJob:
    proc: Optional[subprocess.Popen]
    log_path: pathlib.Path
    start_time: float
    run_dir: pathlib.Path
    artifact_ref: Optional[str] = None
    succeeded: Optional[bool] = None
    xn: Any = None
    context: Optional[Dict[str, str]] = None
    resource_name: Optional[str] = None
    upload_enabled: bool = False
    dry_run: bool = False
    uploaded: bool = False

    def _maybe_upload(self) -> None:
        if self.uploaded or not self.upload_enabled or self.xn is None:
            return
        artifact = upload_outputs_to_xnat(
            self.xn,
            self.context or {},
            self.run_dir,
            resource_name=self.resource_name or "xnat_pipelines_out",
        )
        if artifact:
            self.artifact_ref = artifact
        self.uploaded = True

    def status(self) -> str:
        if self.proc is None:
            return "Prepared"
        code = self.proc.poll()
        if code is None:
            return "Running"
        return "Complete" if code == 0 else "Failed"

    def wait(self, timeout: int = 3600, poll: float = 1.0):
        if self.proc is None:
            if self.upload_enabled and not self.dry_run:
                self._maybe_upload()
            return
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.succeeded = False
            raise
        self.succeeded = (self.proc.returncode == 0)
        if self.succeeded:
            self._maybe_upload()

    def stdout_tail(self, n: int = 2000) -> str:
        try:
            data = self.log_path.read_text(errors="ignore")
            return data[-n:]
        except FileNotFoundError:
            return ""

    def cancel(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def refresh(self) -> None:
        if self.proc:
            self.proc.poll()

class LocalBackend:
    def __init__(self, xnat_session=None, routes: Optional[Dict[str, str]] = None, workdir: Optional[str] = None, engine: str = "docker", io: Optional[Dict[str, Any]] = None, dry_run: bool = False):
        self.xn = xnat_session
        self.routes = routes or {}
        self.workdir = pathlib.Path(workdir or "./xnat_local_runs").absolute()
        self.engine = engine  # 'docker' | 'podman'
        self.io = io or {}
        self.dry_run = dry_run
        self.workdir.mkdir(parents=True, exist_ok=True)

    def _stage(self, context: Dict[str, str]) -> pathlib.Path:
        run_dir = self.workdir / f"run_{int(time.time())}"
        ensure_dirs(run_dir)
        if self.io.get("download", False):
            filters = self.io.get("resource_filters", {})
            stage_from_xnat(self.xn, context, run_dir, resource_filters=filters)
        (run_dir / "context.json").write_text(json.dumps(context, indent=2))
        return run_dir

    def _build_run_cmd(self, image: str, run_dir: pathlib.Path, inputs: Dict[str, Any], cmd_raw: Optional[Dict[str,Any]]) -> List[str]:
        # Map per schema
        extra_args, env_map = map_inputs_and_mounts(cmd_raw or {}, inputs)
        in_mnt, out_mnt = resolve_mounts(cmd_raw or {})
        env_flags = []
        for k, v in env_map.items():
            env_flags += ["-e", f"{k}={v}"]
        return [
            self.engine, "run", "--rm",
            "-v", f"{str(run_dir / 'input')}:{in_mnt}",
            "-v", f"{str(run_dir / 'output')}:{out_mnt}",
            *env_flags,
            image,
            *extra_args
        ]

    def run(self, command_ref: str, context: Dict[str, str], inputs: Dict[str, Any]) -> "JobHandle":
        from ..executor import JobHandle

        image = command_ref
        cmd_raw = None
        if self.xn is not None:
            cc = ContainerClient.from_xnat(self.xn, routes=self.routes)
            cmd = cc.get_command(command_ref)
            image = cmd.image or cmd.name
            cmd_raw = cmd.raw

        run_dir = self._stage(context)
        log_path = run_dir / "run.log"
        cmd = self._build_run_cmd(image=image, run_dir=run_dir, inputs=inputs, cmd_raw=cmd_raw)

        # Persist a tiny run manifest to support dashboard
        manifest = {
            "command": command_ref,
            "image": image,
            "context": context,
            "inputs": inputs,
            "time": int(time.time()),
            "cmd": cmd
        }
        (run_dir / "run.json").write_text(json.dumps(manifest, indent=2))

        upload_enabled = bool(self.io.get("upload") and self.xn is not None)
        resource_name = self.io.get("resource_name")

        if self.dry_run:
            log_path.write_text("DRY RUN\n" + " ".join(shlex.quote(c) for c in cmd))
            proc = None
        else:
            with open(log_path, "w") as lf:
                lf.write("CMD: " + " ".join(shlex.quote(c) for c in cmd) + "\n\n")
            proc = subprocess.Popen(cmd, stdout=open(log_path, "a"), stderr=subprocess.STDOUT)

        return JobHandle(
            backend="local",
            job_id=run_dir.name,
            _impl=_LocalJob(
                proc=proc,
                log_path=log_path,
                start_time=time.time(),
                run_dir=run_dir,
                xn=self.xn if upload_enabled else None,
                context=context if upload_enabled else None,
                resource_name=resource_name if upload_enabled else None,
                upload_enabled=upload_enabled,
                dry_run=self.dry_run,
            ),
        )
