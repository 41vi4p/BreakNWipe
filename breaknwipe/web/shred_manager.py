"""
Shred Job Manager for BreakNWipe Web Interface

Copied from verify_manager.py's exact skeleton (dataclass job + RLock +
ThreadPoolExecutor + start/get/cancel/callback/_notify/_run) -- this is the
fourth near-identical background-job manager (after wipe/recovery/verify).
CLAUDE.md flags that a fourth one of this shape should "consider factoring a
shared base rather than copying again"; that factoring is deliberately NOT
done as part of adding this feature -- refactoring the three existing,
already-shipped managers carries real regression risk that has nothing to do
with shredding, so it's left as a separate, focused change to propose on its
own.

Shredding a batch of files can take a while (multi-pass overwrite of
potentially large files), so it runs as a background job with progress
tracked here, same rationale as the other three.
"""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..device.shredder import shred_files

logger = logging.getLogger(__name__)


@dataclass
class ShredJob:
    job_id: str
    partition: str
    paths: List[str]
    algorithm: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    current_file: str = ""
    files_done: int = 0
    total_files: int = 0
    current_pass: int = 0
    total_passes: int = 0
    bytes_written: int = 0
    total_bytes: int = 0
    percent: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "partition": self.partition,
            "paths": self.paths,
            "algorithm": self.algorithm,
            "status": self.status,
            "current_file": self.current_file,
            "files_done": self.files_done,
            "total_files": self.total_files,
            "current_pass": self.current_pass,
            "total_passes": self.total_passes,
            "bytes_written": self.bytes_written,
            "total_bytes": self.total_bytes,
            "percent": self.percent,
            "result": self.result,
            "error": self.error,
        }


class ShredSessionManager:
    """Runs file-shred jobs in a background thread pool."""

    def __init__(self, max_concurrent: int = 2):
        self.jobs: Dict[str, ShredJob] = {}
        self.progress_callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._lock = threading.RLock()

    def start_shred(self, partition: str, paths: List[str], algorithm: str,
                     algo_kwargs: Optional[dict] = None) -> str:
        job_id = str(uuid.uuid4())
        job = ShredJob(job_id=job_id, partition=partition, paths=paths, algorithm=algorithm,
                        total_files=len(paths))
        with self._lock:
            self.jobs[job_id] = job
            self.progress_callbacks[job_id] = []
            self.cancel_events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id, algo_kwargs or {})
        return job_id

    def get_job(self, job_id: str) -> Optional[ShredJob]:
        with self._lock:
            return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            event = self.cancel_events.get(job_id)
            job = self.jobs.get(job_id)
            if event and job and job.status in ("pending", "running"):
                event.set()
                return True
            return False

    def add_progress_callback(self, job_id: str, callback: Callable[[Dict[str, Any]], None]):
        with self._lock:
            if job_id in self.progress_callbacks:
                self.progress_callbacks[job_id].append(callback)

    def _notify(self, job_id: str):
        with self._lock:
            callbacks = list(self.progress_callbacks.get(job_id, []))
            job = self.jobs.get(job_id)
        if job is None:
            return
        payload = job.to_dict()
        for cb in callbacks:
            try:
                cb(payload)
            except Exception:
                logger.debug("shred progress callback raised", exc_info=True)

    def _run(self, job_id: str, algo_kwargs: dict):
        with self._lock:
            job = self.jobs[job_id]
            job.status = "running"
            cancel_event = self.cancel_events[job_id]
        self._notify(job_id)

        def on_progress(payload: Dict[str, Any]):
            with self._lock:
                j = self.jobs.get(job_id)
                if not j:
                    return
                status = payload.get("status")
                if status in ("running", "completed"):
                    # "completed" here just means shred_files() finished its
                    # loop -- the manager still derives the real terminal
                    # status (completed/failed/cancelled) from the returned
                    # result below, so don't let this overwrite a cancellation
                    # that raced in.
                    if j.status != "cancelled":
                        j.status = "running"
                if payload.get("current_file") is not None:
                    j.current_file = payload["current_file"]
                if payload.get("files_done") is not None:
                    j.files_done = payload["files_done"]
                if payload.get("total_files") is not None:
                    j.total_files = payload["total_files"]
                if payload.get("current_pass") is not None:
                    j.current_pass = payload["current_pass"]
                if payload.get("total_passes") is not None:
                    j.total_passes = payload["total_passes"]
                if payload.get("bytes_written") is not None:
                    j.bytes_written = payload["bytes_written"]
                if payload.get("total_bytes") is not None:
                    j.total_bytes = payload["total_bytes"]
                if payload.get("percent") is not None:
                    j.percent = payload["percent"]
                j.updated_at = datetime.now()
            self._notify(job_id)

        try:
            result = shred_files(
                job.partition, job.paths, job.algorithm, algo_kwargs,
                progress_callback=on_progress, cancel_event=cancel_event
            )
        except Exception as e:
            logger.exception(f"Shred job {job_id} crashed")
            with self._lock:
                job.status = "failed"
                job.error = str(e)
            self._notify(job_id)
            return

        with self._lock:
            if result.cancelled:
                job.status = "cancelled"
            elif result.refused:
                job.status = "failed"
                job.error = result.refusal_reason
            elif result.failed and not result.shredded:
                job.status = "failed"
                job.error = "All requested files failed -- see per-file results."
            else:
                job.status = "completed"
                job.percent = 100.0
            job.result = result.to_dict()
        self._notify(job_id)
