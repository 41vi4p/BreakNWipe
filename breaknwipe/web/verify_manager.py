"""
Verify (Erasure Check) Job Manager for BreakNWipe Web Interface

Mirrors RecoverySessionManager's in-memory session/callback pattern: an
erasure check (statistical sampling of a raw device, optionally at "paranoid"
depth reading up to 100MB) can take a while, so it runs as a background job
with progress tracked here rather than blocking a request, and can be
cancelled mid-check.
"""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..device.erasure_check import check_erasure

logger = logging.getLogger(__name__)


@dataclass
class VerifyJob:
    job_id: str
    device: str
    depth: str
    status: str = "pending"  # pending, sampling, cross_checking, completed, failed, cancelled
    percent: Optional[float] = None
    samples_done: int = 0
    total_samples: int = 0
    eta_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "device": self.device,
            "depth": self.depth,
            "status": self.status,
            "percent": self.percent,
            "samples_done": self.samples_done,
            "total_samples": self.total_samples,
            "eta_seconds": self.eta_seconds,
            "result": self.result,
            "error": self.error,
        }


class VerifySessionManager:
    """Runs erasure-check jobs in a background thread pool."""

    def __init__(self, max_concurrent: int = 2):
        self.jobs: Dict[str, VerifyJob] = {}
        self.progress_callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._lock = threading.RLock()

    def start_check(self, device: str, depth: str) -> str:
        job_id = str(uuid.uuid4())
        job = VerifyJob(job_id=job_id, device=device, depth=depth)
        with self._lock:
            self.jobs[job_id] = job
            self.progress_callbacks[job_id] = []
            self.cancel_events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id)
        return job_id

    def get_job(self, job_id: str) -> Optional[VerifyJob]:
        with self._lock:
            return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            event = self.cancel_events.get(job_id)
            job = self.jobs.get(job_id)
            if event and job and job.status in ("pending", "sampling", "cross_checking"):
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
                logger.debug("verify progress callback raised", exc_info=True)

    def _run(self, job_id: str):
        with self._lock:
            job = self.jobs[job_id]
            job.status = "sampling"
            cancel_event = self.cancel_events[job_id]
        self._notify(job_id)

        def on_progress(payload: Dict[str, Any]):
            with self._lock:
                j = self.jobs.get(job_id)
                if not j:
                    return
                status = payload.get("status")
                if status in ("sampling", "cross_checking", "cancelled", "completed"):
                    j.status = status
                if payload.get("percent") is not None:
                    j.percent = payload["percent"]
                if payload.get("samples_done") is not None:
                    j.samples_done = payload["samples_done"]
                if payload.get("total_samples") is not None:
                    j.total_samples = payload["total_samples"]
                if "eta_seconds" in payload:
                    j.eta_seconds = payload["eta_seconds"]
                j.updated_at = datetime.now()
            self._notify(job_id)

        try:
            result = check_erasure(
                job.device, job.depth, progress_callback=on_progress, cancel_event=cancel_event
            )
        except Exception as e:
            logger.exception(f"Verify job {job_id} crashed")
            with self._lock:
                job.status = "failed"
                job.error = str(e)
            self._notify(job_id)
            return

        with self._lock:
            if result.cancelled:
                job.status = "cancelled"
            elif result.refused or result.error:
                job.status = "failed"
                job.error = result.refusal_reason if result.refused else result.error
            else:
                job.status = "completed"
                job.percent = 100.0
            job.result = result.to_dict()
        self._notify(job_id)
