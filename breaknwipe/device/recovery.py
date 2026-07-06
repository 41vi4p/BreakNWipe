"""
Deleted-File Recovery Module

Two complementary approaches, both shelling out to well-known forensic tools
(same pattern as the rest of device/):

  1. Filesystem-aware undelete via The Sleuth Kit (`fls` to list deleted
     entries, `icat` to extract one by its metadata address). This recovers
     files *with their real names* on NTFS / FAT / exFAT — the common
     "I accidentally deleted files off my USB stick / SD card / camera / Windows
     drive" case. On ext4 it's limited: ext4 nulls an inode's block pointers on
     delete, so deleted files show up as nameless, zero-length "orphans" — we
     surface that honestly and point the user at the deep scan instead.

  2. Deep carve via PhotoRec (`photorec`), signature-based recovery that finds
     file *bodies* by content across any/damaged filesystem (including ext4),
     at the cost of losing the original filenames.

Honest framing (baked into the UI too): recovery only works while the data
hasn't been overwritten. After a real BreakNWipe algorithm wipe, nothing is
recoverable — this module is for accidents, not for undoing a wipe.

Safety: scanning is read-only. Recovery only ever *writes* to a caller-chosen
output directory, and refuses if that directory lives on the same device it's
recovering from (which would overwrite the very data being recovered).
"""

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .filesystem import (
    InvalidDevicePathError,
    get_filesystem_type,
    get_mount_point,
    validate_block_device_path,
)

logger = logging.getLogger(__name__)

# Map our filesystem names to The Sleuth Kit's -f values (auto-detect if unknown).
_TSK_FS = {
    "ext2": "ext", "ext3": "ext", "ext4": "ext",
    "vfat": "fat", "fat": "fat", "fat12": "fat", "fat16": "fat", "fat32": "fat", "msdos": "fat",
    "exfat": "exfat",
    "ntfs": "ntfs",
    "hfsplus": "hfs", "hfs": "hfs",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class RecoverableFile:
    inode: str            # TSK metadata address, e.g. "64" or "64-128-2"
    path: str             # full path within the filesystem
    name: str             # basename
    size: int = 0
    deleted_time: str = ""
    file_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inode": self.inode,
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "deleted_time": self.deleted_time,
            "file_type": self.file_type,
        }


@dataclass
class ScanResult:
    partition: str
    filesystem: Optional[str] = None
    files: List[RecoverableFile] = field(default_factory=list)
    note: str = ""
    error: str = ""
    refused: bool = False
    refusal_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "filesystem": self.filesystem,
            "files": [f.to_dict() for f in self.files],
            "note": self.note,
            "error": self.error,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
        }


@dataclass
class RecoverResult:
    partition: str
    output_dir: str
    requested: int = 0
    recovered: int = 0
    recovered_files: List[str] = field(default_factory=list)
    error: str = ""
    refused: bool = False
    refusal_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "output_dir": self.output_dir,
            "requested": self.requested,
            "recovered": self.recovered,
            "recovered_files": self.recovered_files,
            "error": self.error,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
        }


def recovery_tools() -> Dict[str, bool]:
    """Which recovery tools are installed."""
    return {
        "fls": bool(shutil.which("fls")),
        "icat": bool(shutil.which("icat")),
        "photorec": bool(shutil.which("photorec")),
    }


def _backing_device(path: str) -> str:
    """The device backing a filesystem path (e.g. an output dir), via df."""
    try:
        r = subprocess.run(["df", "--output=source", path], capture_output=True, text=True, timeout=10)
        lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        return lines[-1] if len(lines) >= 2 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def scan_deleted(partition: str, filesystem: Optional[str] = None) -> ScanResult:
    """List recoverable deleted files on a partition (read-only)."""
    result = ScanResult(partition=partition)

    try:
        validate_block_device_path(partition)
    except InvalidDevicePathError as e:
        result.refused = True
        result.refusal_reason = str(e)
        return result

    if not shutil.which("fls"):
        result.refused = True
        result.refusal_reason = "'fls' is not installed (package: sleuthkit)."
        return result

    fstype = filesystem or get_filesystem_type(partition)
    result.filesystem = fstype

    if get_mount_point(partition):
        result.note = (
            "This partition is mounted. Scanning is read-only and safe, but for the best chance of "
            "recovery, unmount it and avoid writing to it (new writes overwrite deleted data)."
        )

    cmd = ["fls", "-r", "-p", "-d", "-l"]
    tsk = _TSK_FS.get((fstype or "").lower())
    if tsk:
        cmd += ["-f", tsk]
    cmd.append(partition)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        result.error = "The scan timed out (very large filesystem)."
        return result
    except (subprocess.SubprocessError, OSError) as e:
        result.error = f"fls failed: {e}"
        return result

    if proc.returncode != 0 and not proc.stdout:
        result.error = f"fls could not read the filesystem: {proc.stderr.strip()}"
        return result

    orphan_only = True
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        meta = parts[0]
        if "*" not in meta:  # only deleted entries are marked with '*'
            continue
        # meta looks like: "-/r * 64-128-2:"  (type, deleted marker, inode)
        tokens = meta.rstrip(":").split()
        if len(tokens) < 3:
            continue
        ftype = tokens[0]
        inode = tokens[-1]
        path = parts[1] if len(parts) > 1 else ""
        name = path.rsplit("/", 1)[-1]
        # fls -l columns after the name: mtime, atime, ctime, crtime, size, uid, gid
        size = 0
        dtime = ""
        if len(parts) >= 7 and parts[6].isdigit():
            size = int(parts[6])
        if len(parts) >= 3:
            dtime = parts[2]
        if not name.startswith("$OrphanFiles"):
            orphan_only = False
        result.files.append(RecoverableFile(
            inode=inode, path=path, name=name or f"inode-{inode}",
            size=size, deleted_time=dtime, file_type=ftype,
        ))

    if not result.files:
        result.note = result.note or (
            "No recoverable deleted files were found. If this is an ext4 drive, deleted-file names "
            "and metadata are usually gone — try a Deep scan, which recovers file contents by type."
        )
    elif (fstype or "").startswith("ext") and orphan_only:
        result.note = (
            "Only nameless 'orphan' entries were found — normal for ext4, which erases file names on "
            "delete. Use a Deep scan to recover file contents by type instead."
        )

    return result


def recover_files(partition: str, inodes: List[str], output_dir: str,
                  filesystem: Optional[str] = None) -> RecoverResult:
    """Extract the given deleted files (by inode) to output_dir using icat."""
    result = RecoverResult(partition=partition, output_dir=output_dir, requested=len(inodes))

    try:
        validate_block_device_path(partition)
    except InvalidDevicePathError as e:
        result.refused = True
        result.refusal_reason = str(e)
        return result

    if not shutil.which("icat"):
        result.refused = True
        result.refusal_reason = "'icat' is not installed (package: sleuthkit)."
        return result

    # Never recover onto the same device we're reading from.
    src_dev = os.path.realpath(partition)
    dst_dev = os.path.realpath(_backing_device(output_dir) or output_dir)
    if src_dev and dst_dev and (src_dev == dst_dev or _backing_device(output_dir) == partition):
        result.refused = True
        result.refusal_reason = (
            "The output folder is on the same device you're recovering from. Choose a folder on a "
            "different drive — recovering onto the source would overwrite the deleted data."
        )
        return result

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        result.error = f"Could not create output folder: {e}"
        return result

    fstype = filesystem or get_filesystem_type(partition)
    tsk = _TSK_FS.get((fstype or "").lower())

    for inode in inodes:
        safe = _SAFE_NAME.sub("_", inode)
        out_path = os.path.join(output_dir, f"recovered_{safe}")
        cmd = ["icat"]
        if tsk:
            cmd += ["-f", tsk]
        cmd += [partition, inode]
        try:
            with open(out_path, "wb") as fh:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=600)
            if proc.returncode == 0 and os.path.getsize(out_path) > 0:
                result.recovered += 1
                result.recovered_files.append(out_path)
            else:
                # Nothing extractable (overwritten / zero-length) -- drop the empty file.
                if os.path.exists(out_path) and os.path.getsize(out_path) == 0:
                    os.remove(out_path)
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("icat failed for inode %s: %s", inode, e)

    if result.recovered == 0 and not result.error:
        result.error = "Nothing could be extracted — the data was likely already overwritten."
    return result


def _proc_read_bytes(pid: int) -> Optional[int]:
    """Bytes actually read from storage by a process so far, via /proc/<pid>/io.

    PhotoRec has no scripted progress API in /cmd (unattended) mode, and it
    seeks with pread() rather than moving its file descriptor's offset, so
    /proc/<pid>/fdinfo's `pos:` field is useless (it jumps to EOF immediately,
    from PhotoRec's initial size probe, and never moves again). read_bytes is
    the only externally observable signal that tracks real scan activity --
    it's an approximation (PhotoRec fast-skips large empty/duplicate regions,
    so it won't necessarily reach the device's full size), which is why the
    caller clamps the derived percentage below 100 until the process exits.
    """
    try:
        with open(f"/proc/{pid}/io") as f:
            for line in f:
                if line.startswith("read_bytes:"):
                    return int(line.split(":", 1)[1].strip())
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    return None


def deep_scan_recover(
    partition: str,
    output_dir: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> RecoverResult:
    """Signature-carve recoverable file contents with PhotoRec (all filesystems,
    recovers bodies without original names). Writes to output_dir/recovered_carved.

    If given, `progress_callback` is invoked periodically (about once a second)
    with a dict of `status` ("running"/"cancelled"/"completed"), `percent`
    (approximate, see `_proc_read_bytes`), `bytes_processed`, `total_bytes`,
    `rate_bytes_per_sec`, and `eta_seconds`. `cancel_event`, if given, is
    polled to allow stopping a long-running deep scan early.
    """
    result = RecoverResult(partition=partition, output_dir=output_dir)

    try:
        validate_block_device_path(partition)
    except InvalidDevicePathError as e:
        result.refused = True
        result.refusal_reason = str(e)
        return result

    if not shutil.which("photorec"):
        result.refused = True
        result.refusal_reason = "'photorec' is not installed (package: testdisk)."
        return result

    if _backing_device(output_dir) == partition or os.path.realpath(_backing_device(output_dir) or "") == os.path.realpath(partition):
        result.refused = True
        result.refusal_reason = (
            "The output folder is on the same device you're recovering from. Choose a folder on a "
            "different drive."
        )
        return result

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        result.error = f"Could not create output folder: {e}"
        return result

    total_bytes = 0
    try:
        from .hexview import device_size_bytes
        total_bytes = device_size_bytes(partition)
    except Exception:
        total_bytes = 0

    def _emit(status: str, **fields: Any) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback({"status": status, "total_bytes": total_bytes, **fields})
        except Exception:
            logger.debug("recovery progress_callback raised", exc_info=True)

    recup = os.path.join(output_dir, "recovered_carved")
    # Non-interactive batch invocation (verified): search the whole space,
    # enable all file types, recover to `recup`. cwd=output_dir keeps the
    # photorec.log PhotoRec writes into the CURRENT working directory (an
    # undocumented behavior) contained there instead of leaking into the
    # server/CLI process's own cwd.
    cmd = ["photorec", "/log", "/d", recup, "/cmd", partition,
           "wholespace,fileopt,everything,enable,search"]
    try:
        proc = subprocess.Popen(cmd, cwd=output_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError) as e:
        result.error = f"photorec failed to start: {e}"
        return result

    _emit("running", percent=0.0, bytes_processed=0, rate_bytes_per_sec=0.0, eta_seconds=None)

    cancelled = False
    last_bytes = 0
    last_time = time.monotonic()
    while proc.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            proc.terminate()
            cancelled = True
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            break
        time.sleep(1.0)
        read_bytes = _proc_read_bytes(proc.pid)
        now = time.monotonic()
        if read_bytes is not None:
            dt = now - last_time
            rate = (read_bytes - last_bytes) / dt if dt > 0 else 0.0
            percent = min(99.0, read_bytes / total_bytes * 100) if total_bytes > 0 else None
            remaining = max(0, total_bytes - read_bytes) if total_bytes > 0 else None
            eta = remaining / rate if (rate > 0 and remaining is not None) else None
            _emit("running", percent=percent, bytes_processed=read_bytes,
                  rate_bytes_per_sec=rate, eta_seconds=eta)
            last_bytes, last_time = read_bytes, now
    else:
        proc.wait()

    if cancelled:
        result.error = "Cancelled."
        _emit("cancelled", percent=None, bytes_processed=last_bytes, eta_seconds=None)
        return result

    # PhotoRec writes into recup.1, recup.2, ... -- collect the carved files.
    # photorec.log lives directly in output_dir (see cwd= above); skip it and
    # the per-run report.xml, neither of which is recovered content.
    for root, _dirs, files in os.walk(output_dir):
        for fn in files:
            if fn.endswith(".xml") or fn == "photorec.log":
                continue
            result.recovered += 1
            result.recovered_files.append(os.path.join(root, fn))

    if result.recovered == 0 and not result.error:
        result.error = "PhotoRec found no recoverable file signatures (data may be overwritten)."

    _emit("completed", percent=100.0, bytes_processed=total_bytes or last_bytes,
          eta_seconds=0, recovered=result.recovered)
    return result
