"""
File Shredder Module

Securely overwrites and removes individual files on a *mounted* filesystem,
in place -- the opposite operating mode of wipe_engine (which requires an
*unmounted* whole device). Reuses the same pass/pattern machinery as a whole-
device wipe (wipe_engine.algorithms.create_algorithm) and the same per-block
write/flush/fsync durability idiom as wipe_engine.engine.WipeEngine._execute_pass,
applied to a file's own byte range instead of a device's.

Honest limits (surfaced to the caller via assess_reliability(), not hidden):
overwriting a file's bytes in place only destroys the original data if the
filesystem actually reuses those same physical blocks for the write. Two
common cases break that assumption and are detected (not blocked -- the
shred still proceeds, same "warn but don't refuse" stance the Verify/Recovery
pillars already take about their own limits):

  1. SSD/NVMe wear-leveling: the drive's firmware may remap a "same offset"
     write to different physical flash cells, leaving the original cells
     (and their data) intact until a later garbage-collection pass.
  2. Copy-on-write filesystems (btrfs, zfs): a write never modifies the
     original blocks at all -- it always allocates new ones and repoints
     metadata, by design. In-place overwrite provides no destruction there.

Safety model, mirroring recovery.py's posture:
  - list_directory() is read-only.
  - shred_files() only ever touches paths that resolve (via os.path.realpath)
    to *inside* the partition's own mount point -- re-validated independently
    for every path on every call, never trusting that a path merely came from
    a prior list_directory() response (the same defense-in-depth stance as
    server.py's /api/download allowlist and recovered_roots check).
  - Only regular files are shredded. Symlinks are refused outright (following
    one could shred something outside the mount, or merely destroy the link
    while the real data survives) -- never silently followed.
"""

import logging
import os
import stat
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .filesystem import get_filesystem_type, get_mount_point
from ..wipe_engine.algorithms import create_algorithm

logger = logging.getLogger(__name__)

# Copy-on-write filesystems where an in-place overwrite never touches the
# original physical blocks -- see module docstring.
COW_FILESYSTEMS = {"btrfs", "zfs"}

_RENAME_ATTEMPTS = 3


@dataclass
class DirEntry:
    name: str
    path: str  # absolute path on the host filesystem (already validated to be inside the mount)
    is_dir: bool
    size_bytes: int = 0
    mtime: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "is_dir": self.is_dir,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
        }


@dataclass
class DirListing:
    mount_point: str
    path: str  # absolute path of the listed directory
    parent: Optional[str]  # absolute path of the parent dir, or None at the mount root
    entries: List[DirEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mount_point": self.mount_point,
            "path": self.path,
            "parent": self.parent,
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class ShredFileOutcome:
    path: str
    success: bool = False
    bytes_written: int = 0
    passes_completed: int = 0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "success": self.success,
            "bytes_written": self.bytes_written,
            "passes_completed": self.passes_completed,
            "warnings": self.warnings,
            "error": self.error,
        }


@dataclass
class ShredJobResult:
    partition: str
    requested: int
    shredded: int = 0
    failed: int = 0
    cancelled: bool = False
    refused: bool = False
    refusal_reason: Optional[str] = None
    files: List[ShredFileOutcome] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "requested": self.requested,
            "shredded": self.shredded,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "files": [f.to_dict() for f in self.files],
        }


def _resolve_within_mount(mount_point: str, candidate: str) -> Optional[str]:
    """
    Realpath-resolve `candidate` and confirm it lives inside `mount_point`
    (either equal to it or nested under it). Returns the resolved absolute
    path, or None if it escapes -- the anchored-prefix check used throughout
    server.py (/api/download, recovered_roots) to stop a client-supplied path
    from walking outside its intended root via "..", a symlink, or otherwise.
    """
    resolved_mount = os.path.realpath(mount_point)
    resolved = os.path.realpath(candidate)
    if resolved == resolved_mount or resolved.startswith(resolved_mount + os.sep):
        return resolved
    return None


def list_directory(partition: str, rel_path: str = "") -> DirListing:
    """
    List the contents of a directory inside `partition`'s mounted filesystem.
    `rel_path` is relative to the mount point (e.g. "" for the root, or
    "Documents/old" for a subdirectory) -- never an absolute host path chosen
    by the client. Read-only.
    """
    mount_point = get_mount_point(partition)
    if not mount_point:
        raise ValueError(f"'{partition}' is not currently mounted.")

    target = _resolve_within_mount(mount_point, os.path.join(mount_point, rel_path.lstrip("/")))
    if target is None:
        raise ValueError("Requested path is outside the partition's mount point.")
    if not os.path.isdir(target):
        raise ValueError(f"'{target}' is not a directory.")

    entries: List[DirEntry] = []
    with os.scandir(target) as it:
        for entry in it:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            entries.append(DirEntry(
                name=entry.name,
                path=entry.path,
                is_dir=is_dir,
                size_bytes=0 if is_dir else st.st_size,
                mtime=st.st_mtime,
            ))

    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))

    parent = None
    if target != os.path.realpath(mount_point):
        parent = os.path.dirname(target)

    return DirListing(mount_point=mount_point, path=target, parent=parent, entries=entries)


def _rotational_for_partition(partition: str) -> Optional[bool]:
    """
    Whether the partition's backing disk is rotational (HDD, True) or not
    (SSD/NVMe/eMMC, False) -- None if it can't be determined. Resolves the
    partition's own /sys/class/block symlink (which works uniformly for both
    "/dev/sdb1" and a partition-less whole disk like "/dev/sdb") to find its
    parent disk's queue/rotational, without depending on DeviceDetector's
    internal state.
    """
    name = os.path.basename(partition)
    class_link = f"/sys/class/block/{name}"
    try:
        real = os.path.realpath(class_link)
    except OSError:
        return None

    candidates = [real, os.path.dirname(real)]
    for base in candidates:
        rot_file = os.path.join(base, "queue", "rotational")
        try:
            with open(rot_file, "r") as f:
                return bool(int(f.read().strip()))
        except (OSError, ValueError):
            continue
    return None


def assess_reliability(partition: str) -> Dict[str, Any]:
    """
    Best-effort assessment of whether an in-place file overwrite on this
    partition can be trusted to actually destroy the original data. Never
    refuses anything -- callers (the GUI) show this as a warning, not a gate.
    """
    fstype = get_filesystem_type(partition)
    rotational = _rotational_for_partition(partition)

    warnings: List[str] = []
    if rotational is False:
        warnings.append(
            "This looks like an SSD/NVMe drive. Wear-leveling firmware may write new data to "
            "different physical cells than the ones holding the original file, leaving it "
            "recoverable at the hardware level even after this shred completes."
        )
    if (fstype or "").lower() in COW_FILESYSTEMS:
        warnings.append(
            f"'{fstype}' is a copy-on-write filesystem. Overwriting a file never modifies its "
            "original blocks -- it always writes new ones -- so in-place shredding provides no "
            "real guarantee here."
        )

    return {
        "partition": partition,
        "fstype": fstype,
        "rotational": rotational,
        "reliable": len(warnings) == 0,
        "warnings": warnings,
    }


def _random_sibling_name(path: str) -> str:
    directory = os.path.dirname(path)
    return os.path.join(directory, os.urandom(8).hex())


def _overwrite_file(path: str, size: int, passes, on_pass_progress: Callable[[int, int, int], None],
                     cancel_event: Optional[threading.Event]) -> int:
    """
    Overwrite `path`'s existing bytes in place with each pass's pattern,
    reusing the same block seek/write/flush/fsync loop (and durability idiom)
    as wipe_engine.engine.WipeEngine._execute_pass, sized to the file's own
    length rather than a device's. Returns the number of passes fully
    completed (may be less than len(passes) if cancelled).
    """
    total_passes = len(passes)
    passes_completed = 0

    if size == 0:
        return total_passes  # nothing to overwrite; truncate/unlink still applies

    with open(path, "r+b", buffering=0) as fh:
        for pass_info in passes:
            if cancel_event is not None and cancel_event.is_set():
                return passes_completed

            block_size = len(pass_info.pattern)
            position = 0
            while position < size:
                if cancel_event is not None and cancel_event.is_set():
                    return passes_completed
                remaining = size - position
                current_block_size = min(block_size, remaining)
                write_data = pass_info.pattern if current_block_size == block_size else pass_info.pattern[:current_block_size]

                fh.seek(position)
                written = fh.write(write_data)
                fh.flush()
                os.fsync(fh.fileno())

                position += written
                on_pass_progress(pass_info.pass_number, position, size)

            passes_completed += 1

    return passes_completed


def shred_files(partition: str, paths: List[str], algorithm: str, algo_kwargs: Optional[dict] = None,
                 progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                 cancel_event: Optional[threading.Event] = None) -> ShredJobResult:
    """
    Securely overwrite and delete each file in `paths`. Every path is
    independently re-validated to resolve inside `partition`'s mount point
    (defense in depth -- never trusts that a path only came from a prior
    list_directory() call). Continues past a single file's failure so one bad
    path doesn't abort the whole batch, matching recovery.recover_files()'s
    per-item tolerance.
    """
    result = ShredJobResult(partition=partition, requested=len(paths))
    algo_kwargs = algo_kwargs or {}

    mount_point = get_mount_point(partition)
    if not mount_point:
        result.refused = True
        result.refusal_reason = f"'{partition}' is not currently mounted."
        return result

    try:
        algorithm_obj = create_algorithm(algorithm, **algo_kwargs)
    except ValueError as e:
        result.refused = True
        result.refusal_reason = str(e)
        return result

    passes = algorithm_obj.get_passes()
    total_files = len(paths)

    def emit(status: str, current_file: str, files_done: int, current_pass: int, total_passes: int,
              bytes_written: int, total_bytes: int):
        if progress_callback is None:
            return
        percent = (files_done / total_files * 100) if total_files else 100.0
        try:
            progress_callback({
                "status": status,
                "current_file": current_file,
                "files_done": files_done,
                "total_files": total_files,
                "current_pass": current_pass,
                "total_passes": total_passes,
                "bytes_written": bytes_written,
                "total_bytes": total_bytes,
                "percent": percent,
            })
        except Exception:
            logger.debug("shred progress_callback raised", exc_info=True)

    for i, raw_path in enumerate(paths):
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break

        outcome = ShredFileOutcome(path=raw_path)
        result.files.append(outcome)

        # Check for a symlink on the RAW, unresolved path first -- realpath()
        # (used below for the mount-containment check) follows symlinks, so
        # by the time a path has been resolved it's too late to tell whether
        # the original entry was a link; lstat'ing the leaf as literally
        # supplied is the only way to catch it before ever following it.
        try:
            raw_st = os.lstat(raw_path)
        except OSError as e:
            outcome.error = f"Could not stat file: {e}"
            result.failed += 1
            continue

        if stat.S_ISLNK(raw_st.st_mode):
            outcome.error = "Refusing to shred a symlink (would follow it outside the mount, or only destroy the link itself)."
            result.failed += 1
            continue

        resolved = _resolve_within_mount(mount_point, raw_path)
        if resolved is None:
            outcome.error = "Path is outside the partition's mount point -- refused."
            result.failed += 1
            continue

        try:
            st = os.lstat(resolved)
        except OSError as e:
            outcome.error = f"Could not stat file: {e}"
            result.failed += 1
            continue

        # Defensive re-check against a TOCTOU race (something replaced the
        # path with a symlink/non-regular-file between the two lstats above).
        if stat.S_ISLNK(st.st_mode):
            outcome.error = "Refusing to shred a symlink (would follow it outside the mount, or only destroy the link itself)."
            result.failed += 1
            continue
        if not stat.S_ISREG(st.st_mode):
            outcome.error = "Not a regular file -- refused."
            result.failed += 1
            continue
        if st.st_nlink > 1:
            outcome.warnings.append(
                f"This file has {st.st_nlink} hard links; other names pointing to the same data will also be affected."
            )

        size = st.st_size

        def on_pass_progress(current_pass: int, bytes_written: int, total_bytes: int, _resolved=resolved, _i=i):
            emit("running", _resolved, _i, current_pass, len(passes), bytes_written, total_bytes)

        try:
            passes_completed = _overwrite_file(resolved, size, passes, on_pass_progress, cancel_event)
            outcome.passes_completed = passes_completed

            if cancel_event is not None and cancel_event.is_set() and passes_completed < len(passes):
                # Cancelled mid-file (not just between files, which the loop's
                # top-of-iteration check already catches) -- this still counts
                # as a user-requested cancellation for the batch as a whole,
                # not a failure. Mark the file as not-yet-shredded and stop
                # processing the rest of the batch.
                outcome.error = "Cancelled before all passes completed."
                result.cancelled = True
                break

            # Best-effort hardening mirroring GNU `shred -u`: truncate, rename
            # to obscure the filename's length/identity, then unlink. Does
            # NOT defeat filesystem journaling of old directory-entry
            # metadata -- see module docstring's honest-limits framing.
            os.truncate(resolved, 0)
            renamed = resolved
            for _ in range(_RENAME_ATTEMPTS):
                candidate = _random_sibling_name(resolved)
                try:
                    os.rename(renamed, candidate)
                    renamed = candidate
                    break
                except OSError:
                    continue
            os.remove(renamed)

            outcome.success = True
            outcome.bytes_written = size * passes_completed
            result.shredded += 1
        except OSError as e:
            outcome.error = f"Shred failed: {e}"
            result.failed += 1

        emit("running", resolved, i + 1, len(passes), len(passes), size, size)

    if not result.cancelled:
        emit("completed", "", total_files, 0, 0, 0, 0)

    return result
