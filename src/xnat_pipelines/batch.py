from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .executor import Executor, JobHandle

@dataclass
class BatchResult:
    context: Dict[str, str]
    status: str
    job_id: str
    backend: str
    error: Optional[str] = None
    artifact_ref: Optional[str] = None

class BatchRunner:
    def __init__(self, executor: Executor, concurrency: int = 4, retry: Optional[Dict[str, Any]] = None):
        self.executor = executor
        self.concurrency = max(1, int(concurrency))
        self.retry = retry or {}

    def _run_one(self, xnat_session, command_ref: str, context: Dict[str,str], inputs: Dict[str,Any], routes, io, workdir, engine, dry_run) -> BatchResult:
        try:
            job = self.executor.run(
                xnat_session=xnat_session,
                command_ref=command_ref,
                context=context,
                inputs=inputs,
                routes=routes,
                io=io,
                retry=self.retry,
                workdir=workdir,
                engine=engine,
                dry_run=dry_run,
            )
            job.wait()
            # For local with upload requested, artifact_ref handled by executor/backends;
            # here we just collect results.
            return BatchResult(context=context, status=job.status, job_id=job.job_id, backend=job.backend, artifact_ref=job.artifact_ref)
        except Exception as e:
            return BatchResult(context=context, status="Failed", job_id="", backend=self.executor.mode, error=str(e))

    def run_many(self,
                 xnat_session,
                 command_ref: str,
                 contexts: Iterable[Dict[str,str]],
                 inputs: Optional[Dict[str,Any]] = None,
                 routes: Optional[Dict[str,str]] = None,
                 io: Optional[Dict[str,Any]] = None,
                 workdir: Optional[str] = None,
                 engine: str = "docker",
                 dry_run: bool = False) -> List[BatchResult]:
        inputs = inputs or {}
        io = io or {}
        results: List[BatchResult] = []
        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = [ex.submit(self._run_one, xnat_session, command_ref, ctx, inputs, routes, io, workdir, engine, dry_run) for ctx in contexts]
            for fut in as_completed(futures):
                results.append(fut.result())
        return results

    def summary(self, results: List[BatchResult]) -> str:
        total = len(results)
        ok = sum(1 for r in results if r.status.lower() in ("complete","completed","succeeded","done"))
        failed = sum(1 for r in results if r.status.lower() in ("failed","error","aborted"))
        return f"Batch summary: total={total}, succeeded={ok}, failed={failed}"
