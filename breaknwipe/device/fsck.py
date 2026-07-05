"""
Filesystem Repair (fsck) Module

Checks and optionally repairs a filesystem's integrity. This is the highest-
stakes new code in the disk-utility toolkit: unlike the wipe engine (which is
*supposed* to destroy data), fsck operates on a filesystem you want to keep,
and running it incorrectly -- against a mounted filesystem, or a live root
disk -- can itself cause data loss.

Safety model, in order of precedence:
  1. Refuse outright on anything that isn't a real, repairable filesystem
     (whole disks, swap, LUKS/LVM/RAID containers) -- see filesystem.py's
     UNREPAIRABLE_FSTYPES.
  2. Check-only (no --repair) is the default and never modifies anything.
  3. --repair on a mounted partition is always refused. This module NEVER
     unmounts anything itself, unlike the wipe path's DeviceHandler --
     force-unmounting a filesystem you intend to repair (rather than
     destroy) risks corrupting in-flight writes, which defeats the purpose.
     The caller must unmount manually, or (for their own OS's root
     filesystem) use a separate bootable medium -- see docs/LIVE_USB_PLAN.md.
  4. --repair on a system-mounted-type partition, or on btrfs (whose own
     upstream docs discourage `--repair` except when truly necessary),
     requires an explicit `force=True` in addition to `repair=True`.
  5. Every tool invocation always includes a non-interactive flag, so a
     repair can never sit waiting on a prompt.
"""

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .filesystem import (
    UNREPAIRABLE_FSTYPES,
    InvalidDevicePathError,
    get_filesystem_type,
    get_mount_point,
    is_system_mount_point,
    list_partitions,
    validate_block_device_path,
)

logger = logging.getLogger(__name__)

# Per-filesystem-type tool dispatch. `exit_style` distinguishes the standard
# fsck(8) bitmask convention (shared by e2fsck/fsck.fat/fsck.exfat) from the
# simpler binary success/failure convention used by ntfsfix/xfs_repair/btrfs.
FSCK_TOOLS: Dict[str, Dict[str, Any]] = {
    "ext2": {"tool": "e2fsck", "check": ["-f", "-n"], "repair": ["-f", "-y"], "exit_style": "fsck_bitmask"},
    "ext3": {"tool": "e2fsck", "check": ["-f", "-n"], "repair": ["-f", "-y"], "exit_style": "fsck_bitmask"},
    "ext4": {"tool": "e2fsck", "check": ["-f", "-n"], "repair": ["-f", "-y"], "exit_style": "fsck_bitmask"},
    "vfat": {"tool": "fsck.fat", "check": ["-n"], "repair": ["-a"], "exit_style": "fsck_bitmask"},
    "fat": {"tool": "fsck.fat", "check": ["-n"], "repair": ["-a"], "exit_style": "fsck_bitmask"},
    "fat16": {"tool": "fsck.fat", "check": ["-n"], "repair": ["-a"], "exit_style": "fsck_bitmask"},
    "fat32": {"tool": "fsck.fat", "check": ["-n"], "repair": ["-a"], "exit_style": "fsck_bitmask"},
    "msdos": {"tool": "fsck.fat", "check": ["-n"], "repair": ["-a"], "exit_style": "fsck_bitmask"},
    "exfat": {"tool": "fsck.exfat", "check": ["-n"], "repair": ["-y"], "exit_style": "fsck_bitmask"},
    "ntfs": {
        "tool": "ntfsfix", "check": ["-n"], "repair": [], "exit_style": "binary",
        "limited_note": (
            "ntfsfix only clears the dirty/bad-sector flags and schedules a full "
            "check on next Windows boot -- it is not a complete filesystem check "
            "like chkdsk."
        ),
    },
    "xfs": {
        "tool": "xfs_repair", "check": ["-n"], "repair": [], "exit_style": "binary",
        "refuses_mounted": True,  # xfs_repair itself refuses to run on a mounted fs, even with -n
    },
    "btrfs": {
        "tool": "btrfs", "check": ["check"], "repair": ["check", "--repair"], "exit_style": "binary",
        "requires_force_for_repair": True,
        "repair_warning": (
            "btrfs upstream strongly discourages `btrfs check --repair` except "
            "when truly necessary, as it can make things worse on some corruption "
            "patterns."
        ),
    },
}

# Filesystem types that always need --force to repair even when unmounted,
# because the underlying tool's repair mode is itself risky (see FSCK_TOOLS).
_REPAIR_NEEDS_FORCE = {name for name, cfg in FSCK_TOOLS.items() if cfg.get("requires_force_for_repair")}


@dataclass
class FsckResult:
    """Outcome of a filesystem check/repair attempt."""

    partition_path: str
    tool_used: Optional[str] = None
    fstype: Optional[str] = None
    check_only: bool = True
    success: bool = False
    filesystem_clean: Optional[bool] = None
    changes_made: bool = False
    needs_reboot: bool = False
    exit_code: Optional[int] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    raw_output: str = ""
    refused: bool = False
    refusal_reason: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition_path": self.partition_path,
            "tool_used": self.tool_used,
            "fstype": self.fstype,
            "check_only": self.check_only,
            "success": self.success,
            "filesystem_clean": self.filesystem_clean,
            "changes_made": self.changes_made,
            "needs_reboot": self.needs_reboot,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "raw_output": self.raw_output,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "notes": self.notes,
        }


class FilesystemChecker:
    """Checks and (optionally, carefully) repairs a filesystem."""

    def check(
        self,
        partition_path: str,
        repair: bool = False,
        force: bool = False,
        filesystem: Optional[str] = None,
    ) -> FsckResult:
        """
        Check (or, with repair=True, repair) the filesystem on partition_path.

        Args:
            partition_path: the partition to check, e.g. /dev/sdb1 (NOT a
                whole disk like /dev/sdb -- see refusal_reason if you pass one).
            repair: if False (default), only ever runs in check/dry-run mode --
                never modifies anything. If True, actually repairs.
            force: required in addition to repair=True to repair a partition
                mounted at a system location, or a btrfs filesystem.
            filesystem: override the auto-detected filesystem type (rarely needed).

        Returns:
            FsckResult. Check `refused`/`refusal_reason` first -- a refusal is
            not an exception, it's this function correctly declining to do
            something unsafe.
        """
        result = FsckResult(partition_path=partition_path, check_only=not repair)

        try:
            validate_block_device_path(partition_path)
        except InvalidDevicePathError as e:
            result.refused = True
            result.refusal_reason = str(e)
            return result

        fstype = filesystem or get_filesystem_type(partition_path)
        result.fstype = fstype

        if not fstype:
            result.refused = True
            result.refusal_reason = (
                f"No recognizable filesystem on {partition_path}. If this is a whole "
                f"disk (e.g. /dev/sda rather than /dev/sda1), fsck operates on "
                f"individual partitions -- use the info/partitions listing to find one."
            )
            return result

        if fstype in UNREPAIRABLE_FSTYPES:
            result.refused = True
            result.refusal_reason = (
                f"{partition_path} is {fstype}, not a repairable filesystem -- it's a "
                f"container (encryption/volume-management/RAID member) or swap space. "
                f"The unlocked/assembled mapped device underneath is the real target, "
                f"which this tool doesn't handle."
            )
            return result

        tool_config = FSCK_TOOLS.get(fstype)
        if not tool_config:
            result.refused = True
            result.refusal_reason = f"No repair tool configured for filesystem type '{fstype}'."
            return result

        tool_name = tool_config["tool"]
        if not shutil.which(tool_name):
            result.refused = True
            result.refusal_reason = (
                f"'{tool_name}' is not installed -- install it to check/repair {fstype} "
                f"filesystems (e.g. via your distro's package manager)."
            )
            return result

        mount_point = get_mount_point(partition_path)
        is_mounted = mount_point is not None
        is_system = is_system_mount_point(mount_point)

        if repair:
            if is_mounted:
                result.refused = True
                result.refusal_reason = (
                    f"{partition_path} is mounted at {mount_point}. Repairing a mounted "
                    f"filesystem risks corrupting in-flight writes -- unmount it yourself "
                    f"first (this tool will not force-unmount for you), or, if this is your "
                    f"own system's root filesystem, boot from a separate live medium to "
                    f"repair it safely (see docs/LIVE_USB_PLAN.md)."
                )
                return result

            if is_system and not force:
                result.refused = True
                result.refusal_reason = (
                    f"{partition_path} is a system-type mount point ({mount_point} when "
                    f"last mounted). Repairing it requires --force to acknowledge the risk."
                )
                return result

            if fstype in _REPAIR_NEEDS_FORCE and not force:
                result.refused = True
                result.refusal_reason = tool_config.get("repair_warning", "") + " Pass --force to proceed anyway."
                return result

        if tool_config.get("refuses_mounted") and is_mounted:
            result.notes.append(
                f"{tool_name} refuses to run against a mounted filesystem, even in check-only "
                f"mode; unmount {partition_path} first to check it."
            )
            result.refused = True
            result.refusal_reason = result.notes[-1]
            return result

        if tool_config.get("limited_note"):
            result.notes.append(tool_config["limited_note"])
        if is_mounted and not repair:
            result.notes.append(
                f"{partition_path} is currently mounted -- a check-only run is safe, but "
                f"results may be less reliable against a live, changing filesystem."
            )

        args = tool_config["repair"] if repair else tool_config["check"]
        argv = [tool_name] + args + [partition_path]

        result.tool_used = tool_name
        start = time.time()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=None if repair else 300)
            result.exit_code = proc.returncode
            result.raw_output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            result.error = f"{tool_name} timed out during check"
            result.duration_seconds = time.time() - start
            return result
        except (subprocess.SubprocessError, OSError) as e:
            result.error = f"Failed to run {tool_name}: {e}"
            result.duration_seconds = time.time() - start
            return result

        result.duration_seconds = time.time() - start
        self._interpret_exit_code(result, tool_config["exit_style"])
        return result

    def list_repairable_partitions(self, device_path: str) -> List[Dict[str, Any]]:
        """Convenience: list a device's partitions with a fsck-eligibility hint for each."""
        partitions = list_partitions(device_path)
        return [p.to_dict() for p in partitions]

    def _interpret_exit_code(self, result: FsckResult, exit_style: str) -> None:
        """
        Interpret the tool's exit code. e2fsck/fsck.fat/fsck.exfat follow the
        standard fsck(8) bitmask (0=clean, 1=corrected, 2=corrected+reboot,
        4=uncorrected, 8=operational error, 16=usage error, 32=canceled,
        128=shared-library error) -- a naive `== 0` check would misreport a
        successful repair (exit code 1) as a failure. ntfsfix/xfs_repair/btrfs
        use a simpler binary convention instead.
        """
        code = result.exit_code or 0

        if exit_style == "fsck_bitmask":
            result.filesystem_clean = (code == 0)
            result.changes_made = bool(code & 1)
            result.needs_reboot = bool(code & 2)
            uncorrected = bool(code & 4)
            operational_error = bool(code & 8) or bool(code & 16) or bool(code & 128)
            result.success = not operational_error and not uncorrected
            if operational_error:
                result.error = f"{result.tool_used} reported an operational/usage error (exit code {code})"
            elif uncorrected:
                result.error = f"{result.tool_used} found errors it could not correct (exit code {code})"
        else:  # "binary"
            result.filesystem_clean = (code == 0)
            result.changes_made = bool(result.check_only is False and code == 0)
            result.success = (code == 0)
            if code != 0:
                result.error = f"{result.tool_used} exited with code {code}"
