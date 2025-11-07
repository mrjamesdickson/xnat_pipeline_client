from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .executor import Executor, JobHandle

_TERMINAL_STATUSES = {
    "complete",
    "completed",
    "succeeded",
    "done",
    "failed",
    "error",
    "aborted",
    "canceled",
    "cancelled",
}
_SUCCESS_STATUSES = {"complete", "completed", "succeeded", "done"}


@dataclass
class BatchResult:
    context: Dict[str, str]
    status: str
    job_id: str
    backend: str
    error: Optional[str] = None
    artifact_ref: Optional[str] = None
    duration_sec: Optional[float] = None


@dataclass
class QueueEvent:
    event: str  # submitted, status, complete, error
    context: Dict[str, str]
    job_id: str
    status: str
    index: int
    duration_sec: Optional[float] = None
    error: Optional[str] = None


@dataclass
class _QueueEntry:
    context: Dict[str, str]
    job: JobHandle
    index: int
    start_time: float
    last_status: str = ""

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

    def run_queue(
        self,
        xnat_session,
        command_ref: str,
        contexts: Iterable[Dict[str, str]],
        inputs: Optional[Dict[str, Any]] = None,
        routes: Optional[Dict[str, str]] = None,
        io: Optional[Dict[str, Any]] = None,
        workdir: Optional[str] = None,
        engine: str = "docker",
        dry_run: bool = False,
        poll_interval: float = 2.0,
        job_timeout: int = 3600,
        status_callback: Optional[Callable[[QueueEvent], None]] = None,
        inputs_factory: Optional[Callable[[Dict[str, str], int], Dict[str, Any]]] = None,
        terminal_statuses: Optional[Iterable[str]] = None,
    ) -> List[BatchResult]:
        """
        Process contexts using an explicit queue with live polling.

        contexts can be any iterable/generator; jobs are launched lazily up to
        the configured concurrency. status_callback will be invoked when jobs
        are submitted, when their status changes, and when they complete.
        """
        base_inputs = inputs or {}
        io = io or {}
        results: List[BatchResult] = []
        terminal = {s.lower() for s in (terminal_statuses or _TERMINAL_STATUSES)}
        context_iter: Iterator[Dict[str, str]] = iter(contexts)
        active: List[_QueueEntry] = []
        launched = 0
        exhausted = False

        def emit(
            event: str,
            entry: Optional[_QueueEntry],
            status: str,
            error: Optional[str] = None,
            duration: Optional[float] = None,
            context_override: Optional[Dict[str, str]] = None,
        ):
            if not status_callback:
                return
            if entry is None:
                ctx = context_override or {}
                job_id = ""
                idx = launched
            else:
                ctx = context_override or entry.context
                job_id = entry.job.job_id
                idx = entry.index
            status_callback(
                QueueEvent(
                    event=event,
                    context=ctx,
                    job_id=job_id,
                    status=status,
                    index=idx,
                    duration_sec=duration,
                    error=error,
                )
            )

        while active or not exhausted:
            while not exhausted and len(active) < self.concurrency:
                try:
                    context = next(context_iter)
                except StopIteration:
                    exhausted = True
                    break
                if not isinstance(context, dict):
                    raise ValueError("Each context must be a mapping with at least 'level' and 'id'")
                launched += 1
                ctx_inputs = dict(base_inputs)
                if inputs_factory:
                    extra = inputs_factory(context, launched)
                    if extra:
                        ctx_inputs.update(extra)
                try:
                    job = self.executor.run(
                        xnat_session=xnat_session,
                        command_ref=command_ref,
                        context=context,
                        inputs=ctx_inputs,
                        routes=routes,
                        io=io,
                        retry=self.retry,
                        workdir=workdir,
                        engine=engine,
                        dry_run=dry_run,
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        BatchResult(
                            context=context,
                            status="Failed",
                            job_id="",
                            backend=self.executor.mode,
                            error=str(exc),
                            duration_sec=0.0,
                        )
                    )
                    emit("error", None, status=str(exc), error=str(exc), duration=0.0, context_override=context)
                    continue

                entry = _QueueEntry(context=context, job=job, index=launched, start_time=time.time())
                active.append(entry)
                emit("submitted", entry, status="submitted")

            if not active:
                break

            still_running: List[_QueueEntry] = []
            for entry in active:
                error_msg: Optional[str] = None
                try:
                    entry.job.refresh()
                    status = entry.job.status or "Unknown"
                except Exception as exc:  # noqa: BLE001
                    status = "Error"
                    error_msg = str(exc)
                if status != entry.last_status:
                    emit("status", entry, status=status)
                    entry.last_status = status
                normalized = status.lower()
                terminal_hit = normalized in terminal or error_msg is not None
                if terminal_hit:
                    duration = time.time() - entry.start_time
                    try:
                        entry.job.wait(timeout=job_timeout, poll=poll_interval)
                    except Exception as exc:  # noqa: BLE001
                        error_msg = error_msg or str(exc)
                        status = status if status.lower() in terminal else f"Failed ({exc})"
                        normalized = "failed"
                    success = normalized in _SUCCESS_STATUSES and error_msg is None
                    result = BatchResult(
                        context=entry.context,
                        status=status,
                        job_id=entry.job.job_id,
                        backend=entry.job.backend,
                        error=None if success else (error_msg or status),
                        artifact_ref=entry.job.artifact_ref,
                        duration_sec=duration,
                    )
                    results.append(result)
                    emit("complete", entry, status=status, error=result.error, duration=duration)
                else:
                    still_running.append(entry)
            active = still_running
            if active:
                time.sleep(poll_interval)
        return results

    def summary(self, results: List[BatchResult]) -> str:
        total = len(results)
        ok = sum(1 for r in results if r.status.lower() in _SUCCESS_STATUSES)
        failed = sum(1 for r in results if r.status.lower() in {"failed","error","aborted"})
        return f"Batch summary: total={total}, succeeded={ok}, failed={failed}"
