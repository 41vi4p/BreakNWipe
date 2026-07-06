"""
Recovery Job Manager for BreakNWipe Web Interface

Deep (PhotoRec) recovery scans can run for a long time on large drives, so --
mirroring WipeSessionManager's in-memory session/callback pattern -- they run
as background jobs with progress tracked here rather than blocking a request.
"""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..device.recovery import deep_scan_recover

logger = logging.getLogger(__name__)


@dataclass
class RecoveryJob:
    job_id: str
    partition: str
    output_dir: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    percent: Optional[float] = None
    bytes_processed: int = 0
    total_bytes: int = 0
    rate_bytes_per_sec: float = 0.0
    eta_seconds: Optional[float] = None
    recovered: int = 0
    recovered_files: List[str] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "partition": self.partition,
            "output_dir": self.output_dir,
            "status": self.status,
            "percent": self.percent,
            "bytes_processed": self.bytes_processed,
            "total_bytes": self.total_bytes,
            "rate_bytes_per_sec": self.rate_bytes_per_sec,
            "eta_seconds": self.eta_seconds,
            "recovered": self.recovered,
            "recovered_files": self.recovered_files,
            "error": self.error,
        }


class RecoverySessionManager:
    """Runs deep-scan recovery jobs in a background thread pool."""

    def __init__(self, max_concurrent: int = 2):
        self.jobs: Dict[str, RecoveryJob] = {}
        self.progress_callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._lock = threading.RLock()

    def start_deep_scan(self, partition: str, output_dir: str) -> str:
        job_id = str(uuid.uuid4())
        job = RecoveryJob(job_id=job_id, partition=partition, output_dir=output_dir)
        with self._lock:
            self.jobs[job_id] = job
            self.progress_callbacks[job_id] = []
            self.cancel_events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id)
        return job_id

    def get_job(self, job_id: str) -> Optional[RecoveryJob]:
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
                logger.debug("recovery progress callback raised", exc_info=True)

    def _run(self, job_id: str):
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
                if status in ("running", "cancelled", "completed"):
                    j.status = status
                if payload.get("percent") is not None:
                    j.percent = payload["percent"]
                if payload.get("bytes_processed") is not None:
                    j.bytes_processed = payload["bytes_processed"]
                if payload.get("total_bytes"):
                    j.total_bytes = payload["total_bytes"]
                if payload.get("rate_bytes_per_sec") is not None:
                    j.rate_bytes_per_sec = payload["rate_bytes_per_sec"]
                if "eta_seconds" in payload:
                    j.eta_seconds = payload["eta_seconds"]
                if payload.get("recovered") is not None:
                    j.recovered = payload["recovered"]
                j.updated_at = datetime.now()
            self._notify(job_id)

        try:
            result = deep_scan_recover(
                job.partition, job.output_dir,
                progress_callback=on_progress, cancel_event=cancel_event,
            )
        except Exception as e:
            logger.exception(f"Deep scan job {job_id} crashed")
            with self._lock:
                job.status = "failed"
                job.error = str(e)
            self._notify(job_id)
            return

        with self._lock:
            if job.status != "cancelled":
                job.status = "failed" if result.refused or (result.error and result.recovered == 0) else "completed"
                job.percent = 100.0 if job.status == "completed" else job.percent
            job.recovered = result.recovered
            job.recovered_files = result.recovered_files
            job.error = result.refusal_reason if result.refused else result.error
        self._notify(job_id)
