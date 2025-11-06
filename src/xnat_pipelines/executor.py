from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import time

from .backends.remote import RemoteBackend
from .backends.local import LocalBackend

@dataclass
class JobHandle:
    backend: str
    job_id: str
    _impl: Any
    artifact_ref: Optional[str] = None

    @property
    def status(self) -> str:
        return self._impl.status()

    def wait(self, timeout: int = 3600, poll: float = 2.0) -> "JobHandle":
        self._impl.wait(timeout=timeout, poll=poll)
        return self

    def stdout_tail(self, n: int = 2000) -> str:
        return self._impl.stdout_tail(n=n)

    def cancel(self) -> None:
        return self._impl.cancel()

class Executor:
    def __init__(self, mode: str = "auto"):
        assert mode in ("remote", "local", "auto")
        self.mode = mode

    def run(self,
            xnat_session: Optional[Any],
            command_ref: str,
            context: Dict[str, str],
            inputs: Optional[Dict[str, Any]] = None,
            routes: Optional[Dict[str, str]] = None,
            workdir: Optional[str] = None,
            engine: str = "docker",
            io: Optional[Dict[str, Any]] = None,
            retry: Optional[Dict[str, Any]] = None,
            dry_run: bool = False) -> JobHandle:
        inputs = inputs or {}
        io = io or {}
        retry = retry or {}
        choice = self.mode
        if choice == "auto":
            choice = "remote" if xnat_session is not None else "local"

        attempts = 0
        max_retries = int(retry.get("max_retries", 0))
        backoff = str(retry.get("backoff", "exp"))
        base = int(retry.get("base_sec", 2))
        cap = int(retry.get("cap_sec", 60))

        while True:
            try:
                if choice == "remote":
                    rb = RemoteBackend(xnat_session=xnat_session, routes=routes, io=io)
                    return rb.run(command_ref=command_ref, context=context, inputs=inputs)
                else:
                    lb = LocalBackend(xnat_session=xnat_session, routes=routes, workdir=workdir, engine=engine, io=io, dry_run=dry_run)
                    return lb.run(command_ref=command_ref, context=context, inputs=inputs)
            except Exception as e:
                if attempts >= max_retries:
                    raise
                attempts += 1
                if backoff == "fixed":
                    delay = base
                else:
                    delay = min(cap, base * (2 ** (attempts-1)))
                time.sleep(delay)
