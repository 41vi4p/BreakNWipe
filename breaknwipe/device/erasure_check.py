"""
Erasure Verification Module

Checks whether a device has actually been wiped -- no recoverable data should
remain. Two complementary read-only checks, combined into one verdict:

  1. Statistical sampling of the raw device, via `WipeVerifier`
     (breaknwipe/wipe_engine/verification.py): Shannon entropy, repeated-
     pattern detection, and known file-format magic bytes, at a chosen depth
     (quick / comprehensive / paranoid).
  2. A best-effort recovery cross-check: if any partition or filesystem is
     still recognizable, run the same quick-scan undelete (`fls`, see
     device/recovery.py) used by the Recover feature and confirm it finds
     nothing recoverable *by name*. A freshly wiped drive usually has NO
     recognizable filesystem at all -- that's a good sign, not a failure, and
     is reported as such rather than as an error.

Never writes to the device.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .filesystem import InvalidDevicePathError, list_partitions, validate_block_device_path
from .hexview import device_size_bytes
from .recovery import scan_deleted
from ..wipe_engine.verification import WipeVerifier

logger = logging.getLogger(__name__)


@dataclass
class PartitionRecoveryCheck:
    partition: str
    filesystem: Optional[str]
    named_files_found: int
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "filesystem": self.filesystem,
            "named_files_found": self.named_files_found,
            "note": self.note,
        }


@dataclass
class ErasureCheckResult:
    device: str
    depth: str
    passed: bool = False
    cancelled: bool = False
    samples_checked: int = 0
    avg_entropy: float = 0.0
    pattern_detections: int = 0
    pattern_detection_percent: float = 0.0
    signature_hits: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    partition_checks: List[PartitionRecoveryCheck] = field(default_factory=list)
    error: str = ""
    refused: bool = False
    refusal_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "depth": self.depth,
            "passed": self.passed,
            "cancelled": self.cancelled,
            "samples_checked": self.samples_checked,
            "avg_entropy": self.avg_entropy,
            "pattern_detections": self.pattern_detections,
            "pattern_detection_percent": self.pattern_detection_percent,
            "signature_hits": self.signature_hits,
            "notes": self.notes,
            "partition_checks": [p.to_dict() for p in self.partition_checks],
            "error": self.error,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
        }


def check_erasure(
    device_path: str,
    depth: str = "comprehensive",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> ErasureCheckResult:
    """Read-only check of whether device_path appears to have been wiped clean.

    If given, `progress_callback` is invoked periodically with a dict of
    `status` ("sampling"/"cross_checking"/"completed"/"cancelled"),
    `samples_done`, `total_samples`, `percent`, and `eta_seconds` -- forwarded
    from `WipeVerifier.verify_wipe_detailed()` for the sampling phase, with an
    extra `cross_checking` event before the (usually fast) recovery cross-
    check phase. `cancel_event`, if given, can stop a long (paranoid) check
    early; already-cancelled before the cross-check phase, that phase is
    skipped entirely.
    """
    result = ErasureCheckResult(device=device_path, depth=depth)

    def _emit(status: str, **fields: Any) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback({"status": status, **fields})
        except Exception:
            logger.debug("erasure check progress_callback raised", exc_info=True)

    try:
        validate_block_device_path(device_path)
    except InvalidDevicePathError as e:
        result.refused = True
        result.refusal_reason = str(e)
        return result

    try:
        size = device_size_bytes(device_path)
    except Exception as e:
        result.error = f"Could not determine device size: {e}"
        return result

    if size <= 0:
        result.error = "Device reports zero size."
        return result

    def _sampling_progress(payload: Dict[str, Any]) -> None:
        _emit(
            "sampling",
            samples_done=payload.get("samples_done"),
            total_samples=payload.get("total_samples"),
            percent=payload.get("percent"),
            eta_seconds=payload.get("eta_seconds"),
        )

    try:
        stats = WipeVerifier().verify_wipe_detailed(
            device_path, size, depth, progress_callback=_sampling_progress, cancel_event=cancel_event
        )
    except Exception as e:
        logger.exception(f"Erasure check failed for {device_path}")
        result.error = f"Verification failed: {e}"
        return result

    result.passed = stats["passed"]
    result.cancelled = bool(stats.get("cancelled"))
    result.samples_checked = stats["samples_checked"]
    result.avg_entropy = stats["avg_entropy"]
    result.pattern_detections = stats["pattern_detections"]
    result.pattern_detection_percent = stats["pattern_detection_percent"]
    result.signature_hits = stats["signature_hits"]
    result.notes = list(stats["notes"])

    if result.cancelled:
        _emit("cancelled")
        return result

    # Best-effort recovery cross-check: if a filesystem is still recognizable,
    # confirm nothing named is recoverable from it. No recognizable filesystem
    # at all is itself a good sign after a real wipe, not a failure.
    _emit("cross_checking")
    try:
        partitions = list_partitions(device_path)
    except Exception:
        partitions = []

    if not partitions:
        result.notes.append("No recognizable filesystem or partition table -- expected after a wipe.")
    else:
        for p in partitions:
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                _emit("cancelled")
                return result
            if not p.fstype:
                result.partition_checks.append(PartitionRecoveryCheck(
                    partition=p.path, filesystem=None, named_files_found=0,
                    note="No recognizable filesystem.",
                ))
                continue
            try:
                scan = scan_deleted(p.path, filesystem=p.fstype)
            except Exception as e:
                result.partition_checks.append(PartitionRecoveryCheck(
                    partition=p.path, filesystem=p.fstype, named_files_found=0,
                    note=f"Could not scan: {e}",
                ))
                continue
            if scan.refused:
                result.partition_checks.append(PartitionRecoveryCheck(
                    partition=p.path, filesystem=p.fstype, named_files_found=0,
                    note=scan.refusal_reason,
                ))
                continue
            named = [f for f in scan.files if f.name and not f.name.startswith("$OrphanFiles")]
            if named:
                result.passed = False
                result.notes.append(f"{len(named)} named recoverable file(s) still found on {p.path}.")
            result.partition_checks.append(PartitionRecoveryCheck(
                partition=p.path, filesystem=p.fstype, named_files_found=len(named),
                note="Nothing recoverable by name." if not named else f"{len(named)} file(s) still recoverable by name.",
            ))

    _emit("completed")
    return result
