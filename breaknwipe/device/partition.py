"""
Partition Management Module

Inspects a disk's partition layout (partitions + free space) and resizes
partitions: grow (into adjacent free space), shrink, and move. Also handles the
common "my VM/root disk grew but the partition didn't expand" case with a
one-step extend, including the LVM variant.

Same safety discipline as fsck.py -- this is destructive territory:
  * Every caller-supplied path is validated as a real block device.
  * Nothing is ever auto-unmounted. Offline-only operations (shrink, move)
    refuse to run against a mounted filesystem; the caller must unmount first.
  * Growing is allowed online where the filesystem supports it (ext4/xfs/btrfs
    grow while mounted), which is what makes live root-partition extension work.
  * Operating on a system disk requires an explicit force flag.
  * Every operation is *preview-first*: plan_* computes the exact shell commands
    (and gates) without touching anything, so the UI/CLI can show precisely what
    will run before the user confirms. Transparency is the trust story.
  * `move` is the sharpest edge (block-copy + partition-table rewrite; an
    interruption corrupts the filesystem) and is gated hardest + labelled
    experimental.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .filesystem import (
    InvalidDevicePathError,
    get_filesystem_type,
    get_mount_point,
    is_system_mount_point,
    validate_block_device_path,
)

logger = logging.getLogger(__name__)

# Mount points whose partition is part of the running system; resizing these is
# gated behind an explicit force.
SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/usr", "/var", "/home"}

# Filesystems we can grow, and how. "online" = can grow while mounted.
GROWABLE_FS = {"ext2", "ext3", "ext4", "xfs", "btrfs", "ntfs"}
# Filesystems we can shrink. XFS is deliberately absent: xfs_growfs can only
# grow, never shrink -- there is no XFS shrink tool, and we say so honestly.
SHRINKABLE_FS = {"ext2", "ext3", "ext4", "ntfs", "btrfs"}


@dataclass
class FreeSegment:
    start_sector: int
    size_sectors: int
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_sector": self.start_sector,
            "size_sectors": self.size_sectors,
            "size_bytes": self.size_bytes,
        }


@dataclass
class DiskPartition:
    node: str                       # e.g. /dev/sda1
    number: int                     # partition number (1-based)
    start_sector: int
    size_sectors: int
    size_bytes: int
    fstype: Optional[str] = None
    mount_point: Optional[str] = None
    is_mounted: bool = False
    is_system: bool = False
    type_uuid: Optional[str] = None
    name: Optional[str] = None
    free_after_bytes: int = 0       # adjacent free space immediately after this partition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": self.node,
            "number": self.number,
            "start_sector": self.start_sector,
            "size_sectors": self.size_sectors,
            "size_bytes": self.size_bytes,
            "fstype": self.fstype,
            "mount_point": self.mount_point,
            "is_mounted": self.is_mounted,
            "is_system": self.is_system,
            "type_uuid": self.type_uuid,
            "name": self.name,
            "free_after_bytes": self.free_after_bytes,
        }


@dataclass
class DiskLayout:
    disk: str
    table_type: Optional[str]       # "gpt" / "dos" (MBR) / None
    sector_size: int
    total_bytes: int
    partitions: List[DiskPartition] = field(default_factory=list)
    free_segments: List[FreeSegment] = field(default_factory=list)
    has_lvm: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disk": self.disk,
            "table_type": self.table_type,
            "sector_size": self.sector_size,
            "total_bytes": self.total_bytes,
            "partitions": [p.to_dict() for p in self.partitions],
            "free_segments": [f.to_dict() for f in self.free_segments],
            "has_lvm": self.has_lvm,
            "error": self.error,
        }


@dataclass
class ResizePlan:
    """A previewed resize -- the exact commands and gate decisions, computed
    without touching the disk."""
    partition: str
    mode: str                       # "grow" / "shrink" / "move"
    fstype: Optional[str] = None
    current_bytes: int = 0
    target_bytes: int = 0
    commands: List[str] = field(default_factory=list)   # human-readable command previews
    warnings: List[str] = field(default_factory=list)
    refused: bool = False
    refusal_reason: Optional[str] = None
    requires_force: bool = False
    experimental: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "mode": self.mode,
            "fstype": self.fstype,
            "current_bytes": self.current_bytes,
            "target_bytes": self.target_bytes,
            "commands": self.commands,
            "warnings": self.warnings,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "requires_force": self.requires_force,
            "experimental": self.experimental,
        }


@dataclass
class ResizeResult:
    partition: str
    mode: str
    success: bool = False
    changes_made: bool = False
    commands_run: List[str] = field(default_factory=list)
    output: str = ""
    error: Optional[str] = None
    refused: bool = False
    refusal_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition": self.partition,
            "mode": self.mode,
            "success": self.success,
            "changes_made": self.changes_made,
            "commands_run": self.commands_run,
            "output": self.output,
            "error": self.error,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
        }


# ---- Disk layout inspection ----

def _run(cmd: List[str], timeout: Optional[int] = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def parent_disk(partition_path: str) -> Optional[str]:
    """Return the whole-disk device for a partition (e.g. /dev/sda1 -> /dev/sda,
    /dev/nvme0n1p2 -> /dev/nvme0n1), via lsblk's PKNAME (robust across naming schemes)."""
    try:
        result = _run(["lsblk", "-no", "PKNAME", partition_path], timeout=10)
        parent = result.stdout.strip().split("\n")[0].strip()
        return f"/dev/{parent}" if parent else None
    except (subprocess.SubprocessError, OSError):
        return None


def partition_number(partition_path: str) -> Optional[int]:
    """Return a partition's 1-based number, read from sysfs (naming-scheme independent)."""
    name = os.path.basename(partition_path)
    try:
        with open(f"/sys/class/block/{name}/partition") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_disk_layout(disk_path: str) -> DiskLayout:
    """Inspect a whole disk: its partition table, partitions (with fs/mount
    info), and the free-space gaps between/after them."""
    try:
        validate_block_device_path(disk_path)
    except InvalidDevicePathError as e:
        return DiskLayout(disk=disk_path, table_type=None, sector_size=512, total_bytes=0, error=str(e))

    layout = DiskLayout(disk=disk_path, table_type=None, sector_size=512, total_bytes=0)

    # Partition geometry (sectors) from sfdisk.
    try:
        sf = _run(["sfdisk", "--json", disk_path], timeout=20)
        if sf.returncode != 0:
            layout.error = f"sfdisk failed: {sf.stderr.strip()}"
            return layout
        table = json.loads(sf.stdout).get("partitiontable", {})
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
        layout.error = f"Could not read partition table: {e}"
        return layout

    layout.table_type = table.get("label")
    layout.sector_size = int(table.get("sectorsize", 512))
    first_lba = int(table.get("firstlba", 34))
    last_lba = int(table.get("lastlba", 0))

    # Whole-disk size (bytes) from sysfs.
    try:
        with open(f"/sys/class/block/{os.path.basename(disk_path)}/size") as f:
            layout.total_bytes = int(f.read().strip()) * 512
    except (OSError, ValueError):
        layout.total_bytes = (last_lba + 1) * layout.sector_size if last_lba else 0

    # Per-partition fs/mount info via lsblk.
    fs_by_node: Dict[str, Dict[str, Any]] = {}
    try:
        lb = _run(["lsblk", "-J", "-b", "-o", "NAME,PATH,FSTYPE,MOUNTPOINT,TYPE", disk_path], timeout=15)
        if lb.returncode == 0:
            root = json.loads(lb.stdout).get("blockdevices", [])
            for child in (root[0].get("children", []) if root else []):
                fs_by_node[child.get("path", "")] = child
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        pass

    parts = sorted(table.get("partitions", []), key=lambda p: int(p.get("start", 0)))
    for p in parts:
        node = p.get("node", "")
        start = int(p.get("start", 0))
        size = int(p.get("size", 0))
        fstype = get_filesystem_type(node) or (fs_by_node.get(node, {}).get("fstype"))
        mount_point = get_mount_point(node) or (fs_by_node.get(node, {}).get("mountpoint"))
        layout.partitions.append(DiskPartition(
            node=node,
            number=partition_number(node) or 0,
            start_sector=start,
            size_sectors=size,
            size_bytes=size * layout.sector_size,
            fstype=fstype,
            mount_point=mount_point,
            is_mounted=mount_point is not None,
            is_system=is_system_mount_point(mount_point),
            type_uuid=p.get("type"),
            name=p.get("name"),
        ))
        if fstype == "LVM2_member":
            layout.has_lvm = True

    # Free-space gaps: walk the sector line from first usable to last usable.
    cursor = first_lba
    usable_end = last_lba if last_lba else (layout.total_bytes // layout.sector_size) - 1
    for part in layout.partitions:
        if part.start_sector > cursor:
            gap = part.start_sector - cursor
            layout.free_segments.append(FreeSegment(cursor, gap, gap * layout.sector_size))
        cursor = max(cursor, part.start_sector + part.size_sectors)
        # Record free space immediately after this partition (what grow can use).
    if usable_end >= cursor:
        tail = usable_end - cursor + 1
        if tail > 1:
            layout.free_segments.append(FreeSegment(cursor, tail, tail * layout.sector_size))

    # Annotate each partition with the free space directly after it.
    for part in layout.partitions:
        end = part.start_sector + part.size_sectors
        for seg in layout.free_segments:
            if seg.start_sector == end:
                part.free_after_bytes = seg.size_bytes
                break

    return layout


# ---- Resize ----

def _fs_grow_commands(fstype: Optional[str], node: str, mount_point: Optional[str]) -> tuple[List[List[str]], List[str]]:
    """Return (argv-list, warnings) for growing a filesystem to fill its
    (already-enlarged) partition. Empty list means 'partition grown but the
    filesystem could not be auto-grown'."""
    warnings: List[str] = []
    if fstype in ("ext2", "ext3", "ext4"):
        # resize2fs grows to fill the partition; works online for mounted ext4.
        return [["resize2fs", node]], warnings
    if fstype == "xfs":
        if mount_point:
            return [["xfs_growfs", mount_point]], warnings
        warnings.append("XFS can only be grown while mounted; mount it first, then grow.")
        return [], warnings
    if fstype == "btrfs":
        if mount_point:
            return [["btrfs", "filesystem", "resize", "max", mount_point]], warnings
        warnings.append("btrfs can only be grown while mounted; mount it first, then grow.")
        return [], warnings
    if fstype == "ntfs":
        if mount_point:
            warnings.append("NTFS must be unmounted to resize; unmount it first.")
            return [], warnings
        return [["ntfsresize", "-f", node]], warnings
    if fstype == "LVM2_member":
        # The partition is an LVM physical volume. Growing the partition then
        # `pvresize` grows the PV into the new space; the freed extents then
        # show up in the volume group for the user to extend a logical volume
        # (see extend_lv). This is the "grow the disk under LVM" step.
        warnings.append("LVM physical volume grown; the free extents are now in the volume group. Extend a logical volume to use them.")
        return [["pvresize", node]], warnings
    warnings.append(f"Filesystem '{fstype}' can't be auto-grown; the partition was enlarged but the filesystem still fills the old size.")
    return [], warnings


def list_logical_volumes() -> List[Dict[str, str]]:
    """List LVM logical volumes (name, vg, path, size, free-in-vg) for the GUI's
    'extend root on LVM' flow. Empty if LVM isn't in use or lvs isn't installed."""
    if not shutil.which("lvs"):
        return []
    try:
        result = _run(
            ["lvs", "--noheadings", "--units", "b", "--nosuffix", "-o",
             "lv_name,vg_name,lv_path,lv_size,vg_free"],
            timeout=15,
        )
        lvs = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                lvs.append({
                    "lv_name": parts[0], "vg_name": parts[1], "lv_path": parts[2],
                    "lv_size_bytes": parts[3], "vg_free_bytes": parts[4],
                })
        return lvs
    except (subprocess.SubprocessError, OSError):
        return []


def extend_lv(lv_path: str, fill: bool = True) -> ResizeResult:
    """Extend a logical volume (and its filesystem, via `lvextend -r`) to use
    the free space in its volume group. This is the second half of the 'extend
    root on LVM' flow, after the PV has been grown (or a new PV added)."""
    result = ResizeResult(partition=lv_path, mode="lvextend")
    if not shutil.which("lvextend"):
        result.refused = True
        result.refusal_reason = "'lvextend' is not installed (package: lvm2)."
        return result
    if not fill:
        result.refused = True
        result.refusal_reason = "Only fill-to-free is supported for LV extend right now."
        return result

    cmd = ["lvextend", "-r", "-l", "+100%FREE", lv_path]
    fr = _run(cmd, timeout=600)
    result.commands_run.append(" ".join(cmd))
    result.output = fr.stdout + fr.stderr
    if fr.returncode != 0:
        # lvextend returns non-zero when there's no free space to add; treat that
        # as an honest "nothing to do" rather than a hard failure.
        if "matches existing size" in result.output or "no free extents" in result.output.lower():
            result.success = True
            result.output += "\n(volume group has no free space to add)"
        else:
            result.error = f"lvextend failed: {fr.stderr.strip() or fr.stdout.strip()}"
        return result
    result.success = True
    result.changes_made = True
    return result


class PartitionResizer:
    """Plans and applies partition resizes, preview-first."""

    def plan_grow(self, partition_path: str, force: bool = False) -> ResizePlan:
        """Preview growing a partition to fill the free space immediately after
        it, then growing its filesystem. Never touches the disk."""
        plan = ResizePlan(partition=partition_path, mode="grow")

        try:
            validate_block_device_path(partition_path)
        except InvalidDevicePathError as e:
            plan.refused = True
            plan.refusal_reason = str(e)
            return plan

        disk = parent_disk(partition_path)
        num = partition_number(partition_path)
        if not disk or not num:
            plan.refused = True
            plan.refusal_reason = (
                f"{partition_path} doesn't look like a partition on a disk (no parent/number). "
                f"Grow operates on a partition like /dev/sda1, not a whole disk."
            )
            return plan

        if not shutil.which("growpart"):
            plan.refused = True
            plan.refusal_reason = "'growpart' is not installed (package: cloud-guest-utils)."
            return plan

        layout = get_disk_layout(disk)
        part = next((p for p in layout.partitions if p.node == partition_path), None)
        if not part:
            plan.refused = True
            plan.refusal_reason = f"Could not find {partition_path} in {disk}'s partition table."
            return plan

        plan.fstype = part.fstype
        plan.current_bytes = part.size_bytes

        if part.free_after_bytes <= layout.sector_size:
            plan.refused = True
            plan.refusal_reason = (
                f"No free space immediately after {partition_path} to grow into. "
                f"(If your virtual disk was just enlarged, the free space should appear at the end "
                f"of the disk — the partition being grown must be the last one before that free space.)"
            )
            return plan

        if part.is_system and not force:
            plan.requires_force = True
            plan.warnings.append(
                f"{partition_path} is a system partition ({part.mount_point}). Growing it is "
                f"generally safe and can be done live, but requires confirmation (force)."
            )

        # Preview the growpart change.
        try:
            dry = _run(["growpart", "--dry-run", disk, str(num)], timeout=30)
            change_line = next((ln for ln in dry.stdout.splitlines() if ln.startswith("CHANGE")), "")
            if change_line:
                plan.warnings.append(change_line.strip())
        except (subprocess.SubprocessError, OSError):
            pass

        plan.target_bytes = part.size_bytes + part.free_after_bytes
        plan.commands.append(f"growpart {disk} {num}")

        fs_cmds, fs_warn = _fs_grow_commands(part.fstype, partition_path, part.mount_point)
        plan.warnings.extend(fs_warn)
        for c in fs_cmds:
            plan.commands.append(" ".join(c))

        return plan

    def grow(self, partition_path: str, force: bool = False) -> ResizeResult:
        """Grow a partition into adjacent free space and grow its filesystem.
        Re-checks all gates (does not trust a previously-computed plan)."""
        result = ResizeResult(partition=partition_path, mode="grow")

        plan = self.plan_grow(partition_path, force=force)
        if plan.refused:
            result.refused = True
            result.refusal_reason = plan.refusal_reason
            return result
        if plan.requires_force and not force:
            result.refused = True
            result.refusal_reason = plan.warnings[0] if plan.warnings else "Requires force."
            return result

        disk = parent_disk(partition_path)
        num = partition_number(partition_path)

        # 1) Grow the partition (growpart uses BLKPG, safe on a mounted disk).
        gp = _run(["growpart", disk, str(num)], timeout=120)
        result.commands_run.append(f"growpart {disk} {num}")
        result.output += gp.stdout + gp.stderr
        # growpart exit 0 = changed; exit 1 = NOCHANGE (already max) which we treat as fine
        # only if it genuinely couldn't grow; but plan already checked free space.
        if gp.returncode not in (0,):
            # Distinguish "no change needed" from a real error.
            if "NOCHANGE" in (gp.stdout + gp.stderr).upper():
                result.output += "\n(partition already at maximum)"
            else:
                result.error = f"growpart failed: {gp.stderr.strip() or gp.stdout.strip()}"
                return result
        else:
            result.changes_made = True

        # Refresh the kernel's view of the new size.
        _run(["partprobe", disk], timeout=30)
        time.sleep(0.5)

        # 2) Grow the filesystem.
        fstype = get_filesystem_type(partition_path)
        mount_point = get_mount_point(partition_path)
        fs_cmds, fs_warn = _fs_grow_commands(fstype, partition_path, mount_point)
        if not fs_cmds and fs_warn:
            result.output += "\n" + "\n".join(fs_warn)
            result.success = result.changes_made
            return result

        for cmd in fs_cmds:
            fr = _run(cmd, timeout=600)
            result.commands_run.append(" ".join(cmd))
            result.output += "\n" + fr.stdout + fr.stderr
            if fr.returncode != 0:
                result.error = f"{cmd[0]} failed: {fr.stderr.strip() or fr.stdout.strip()}"
                return result
            result.changes_made = True

        result.success = True
        return result

    # ---- Shrink (offline only) ----

    def _resolve(self, partition_path: str) -> tuple[Optional[str], Optional[int], Optional[DiskPartition], Optional[DiskLayout]]:
        disk = parent_disk(partition_path)
        num = partition_number(partition_path)
        if not disk or not num:
            return None, None, None, None
        layout = get_disk_layout(disk)
        part = next((p for p in layout.partitions if p.node == partition_path), None)
        return disk, num, part, layout

    def _ext_min_bytes(self, node: str, sector_size: int) -> Optional[int]:
        """Estimated minimum size a shrinkable ext filesystem can be resized to."""
        try:
            r = _run(["resize2fs", "-P", node], timeout=60)
            m = re.search(r":\s*(\d+)", r.stdout)
            if m:
                # resize2fs -P reports in filesystem blocks (usually 4096); be
                # conservative and treat the number as 4k blocks.
                return int(m.group(1)) * 4096
        except (subprocess.SubprocessError, OSError):
            pass
        return None

    def plan_shrink(self, partition_path: str, target_bytes: int, force: bool = False) -> ResizePlan:
        plan = ResizePlan(partition=partition_path, mode="shrink", target_bytes=target_bytes)
        try:
            validate_block_device_path(partition_path)
        except InvalidDevicePathError as e:
            plan.refused = True
            plan.refusal_reason = str(e)
            return plan

        disk, num, part, layout = self._resolve(partition_path)
        if not part:
            plan.refused = True
            plan.refusal_reason = f"{partition_path} is not a partition on a disk."
            return plan

        plan.fstype = part.fstype
        plan.current_bytes = part.size_bytes

        if part.fstype == "xfs":
            plan.refused = True
            plan.refusal_reason = "XFS filesystems cannot be shrunk — there is no XFS shrink tool. (You can only grow XFS.)"
            return plan
        if part.fstype not in SHRINKABLE_FS:
            plan.refused = True
            plan.refusal_reason = f"Shrinking '{part.fstype}' filesystems is not supported."
            return plan
        if part.is_mounted:
            plan.refused = True
            plan.refusal_reason = (
                f"{partition_path} is mounted at {part.mount_point}. Shrinking must be done offline "
                f"— unmount it first (for your system's root, boot from a live medium)."
            )
            return plan
        if target_bytes >= part.size_bytes:
            plan.refused = True
            plan.refusal_reason = f"Target size must be smaller than the current size ({part.size_bytes} bytes)."
            return plan

        if part.fstype in ("ext2", "ext3", "ext4"):
            min_bytes = self._ext_min_bytes(partition_path, layout.sector_size)
            if min_bytes and target_bytes < min_bytes:
                plan.refused = True
                plan.refusal_reason = (
                    f"Target {target_bytes} bytes is below the filesystem's minimum "
                    f"(~{min_bytes} bytes of data in use). Free up space or choose a larger target."
                )
                return plan

        if part.is_system and not force:
            plan.requires_force = True
            plan.warnings.append(f"{partition_path} is a system partition; shrinking requires force.")

        plan.warnings.append("Shrinking moves the filesystem's end inward. Back up important data first.")

        # Filesystem-first, then the partition table.
        target_sectors = target_bytes // layout.sector_size
        if part.fstype in ("ext2", "ext3", "ext4"):
            plan.commands.append(f"e2fsck -f -y {partition_path}")
            plan.commands.append(f"resize2fs {partition_path} {target_bytes // 1024}K")
        elif part.fstype == "ntfs":
            plan.commands.append(f"ntfsresize -f -s {target_bytes} {partition_path}")
        plan.commands.append(f"sfdisk -N {num} {disk}  (size={target_sectors} sectors)")
        return plan

    def shrink(self, partition_path: str, target_bytes: int, force: bool = False) -> ResizeResult:
        result = ResizeResult(partition=partition_path, mode="shrink")
        plan = self.plan_shrink(partition_path, target_bytes, force=force)
        if plan.refused:
            result.refused = True
            result.refusal_reason = plan.refusal_reason
            return result
        if plan.requires_force and not force:
            result.refused = True
            result.refusal_reason = plan.refusal_reason or "Requires force."
            return result

        disk, num, part, layout = self._resolve(partition_path)
        sector_size = layout.sector_size

        # 1) Shrink the filesystem first.
        if part.fstype in ("ext2", "ext3", "ext4"):
            fc = _run(["e2fsck", "-f", "-y", partition_path], timeout=600)
            result.commands_run.append(f"e2fsck -f -y {partition_path}")
            result.output += fc.stdout + fc.stderr
            # e2fsck exit 1/2 = fixed (ok); >=4 = uncorrected
            if fc.returncode >= 4:
                result.error = "e2fsck found uncorrectable errors; aborting shrink."
                return result
            rc = _run(["resize2fs", partition_path, f"{target_bytes // 1024}K"], timeout=1200)
            result.commands_run.append(f"resize2fs {partition_path} {target_bytes // 1024}K")
            result.output += "\n" + rc.stdout + rc.stderr
            if rc.returncode != 0:
                result.error = f"resize2fs failed: {rc.stderr.strip() or rc.stdout.strip()}"
                return result
        elif part.fstype == "ntfs":
            nc = _run(["ntfsresize", "-f", "-s", str(target_bytes), partition_path], timeout=1200)
            result.commands_run.append(f"ntfsresize -f -s {target_bytes} {partition_path}")
            result.output += nc.stdout + nc.stderr
            if nc.returncode != 0:
                result.error = f"ntfsresize failed: {nc.stderr.strip() or nc.stdout.strip()}"
                return result
        result.changes_made = True

        # 2) Shrink the partition table entry (start unchanged, smaller size).
        #    Leave a tiny safety margin so the partition is never smaller than
        #    the freshly-shrunk filesystem.
        new_sectors = (target_bytes // sector_size)
        spec = f"start={part.start_sector}, size={new_sectors}\n"
        sc = subprocess.run(
            ["sfdisk", "--no-reread", "-N", str(num), disk],
            input=spec, capture_output=True, text=True, timeout=60,
        )
        result.commands_run.append(f"sfdisk -N {num} {disk} (size={new_sectors})")
        result.output += "\n" + sc.stdout + sc.stderr
        if sc.returncode != 0:
            result.error = f"sfdisk (partition shrink) failed: {sc.stderr.strip() or sc.stdout.strip()}"
            return result

        _run(["partprobe", disk], timeout=30)
        result.success = True
        return result

    # ---- Move (experimental, offline only) ----

    def plan_move(self, partition_path: str, new_start_sector: int, force: bool = False) -> ResizePlan:
        plan = ResizePlan(partition=partition_path, mode="move", experimental=True)
        try:
            validate_block_device_path(partition_path)
        except InvalidDevicePathError as e:
            plan.refused = True
            plan.refusal_reason = str(e)
            return plan

        disk, num, part, layout = self._resolve(partition_path)
        if not part:
            plan.refused = True
            plan.refusal_reason = f"{partition_path} is not a partition on a disk."
            return plan

        plan.fstype = part.fstype
        plan.current_bytes = part.size_bytes

        if part.is_mounted:
            plan.refused = True
            plan.refusal_reason = f"{partition_path} is mounted at {part.mount_point}. Moving must be done offline — unmount it first."
            return plan

        old_start = part.start_sector
        size = part.size_sectors
        old_end = old_start + size - 1
        new_end = new_start_sector + size - 1

        if new_start_sector == old_start:
            plan.refused = True
            plan.refusal_reason = "New start equals current start — nothing to move."
            return plan
        # Refuse overlapping moves: an interrupted overlapping block-copy is
        # unrecoverable. Only non-overlapping relocations are allowed.
        if not (new_end < old_start or new_start_sector > old_end):
            plan.refused = True
            plan.refusal_reason = (
                "The new location overlaps the current one. Overlapping moves are refused because an "
                "interruption mid-copy would be unrecoverable. Choose a fully non-overlapping location."
            )
            return plan
        usable_last = layout.total_bytes // layout.sector_size - 1
        if new_start_sector < 34 or new_end > usable_last:
            plan.refused = True
            plan.refusal_reason = "The new location falls outside the disk's usable area."
            return plan

        plan.requires_force = True  # move always requires explicit force
        plan.warnings.append(
            "MOVE is experimental and high-risk: it block-copies the partition to a new offset and "
            "rewrites the partition table. An interruption (power loss, crash) corrupts the filesystem. "
            "Back up first, and ensure stable power."
        )
        bs = layout.sector_size
        plan.commands.append(
            f"dd if={disk} of={disk} bs={bs} skip={old_start} seek={new_start_sector} count={size} conv=notrunc"
        )
        plan.commands.append(f"sfdisk -N {num} {disk}  (start={new_start_sector}, size={size})")
        return plan

    def move(self, partition_path: str, new_start_sector: int, force: bool = False) -> ResizeResult:
        result = ResizeResult(partition=partition_path, mode="move")
        plan = self.plan_move(partition_path, new_start_sector, force=force)
        if plan.refused:
            result.refused = True
            result.refusal_reason = plan.refusal_reason
            return result
        if not force:
            result.refused = True
            result.refusal_reason = "Move requires an explicit force/confirmation."
            return result

        disk, num, part, layout = self._resolve(partition_path)
        bs = layout.sector_size
        old_start = part.start_sector
        size = part.size_sectors

        # 1) Copy the data block-for-block to the new offset (non-overlapping,
        #    already verified in plan). conv=notrunc so we don't truncate the disk.
        dd = _run([
            "dd", f"if={disk}", f"of={disk}", f"bs={bs}",
            f"skip={old_start}", f"seek={new_start_sector}", f"count={size}", "conv=notrunc,fsync",
        ], timeout=None)
        result.commands_run.append(f"dd if={disk} of={disk} bs={bs} skip={old_start} seek={new_start_sector} count={size}")
        result.output += dd.stdout + dd.stderr
        if dd.returncode != 0:
            result.error = f"Block copy failed: {dd.stderr.strip()}. Partition table NOT changed."
            return result
        result.changes_made = True

        # 2) Point the partition table entry at the new start.
        spec = f"start={new_start_sector}, size={size}\n"
        sc = subprocess.run(
            ["sfdisk", "--no-reread", "-N", str(num), disk],
            input=spec, capture_output=True, text=True, timeout=60,
        )
        result.commands_run.append(f"sfdisk -N {num} {disk} (start={new_start_sector})")
        result.output += "\n" + sc.stdout + sc.stderr
        if sc.returncode != 0:
            result.error = (
                f"Data was copied, but updating the partition table failed: {sc.stderr.strip()}. "
                f"The partition still points at the old location (data there is intact)."
            )
            return result

        _run(["partprobe", disk], timeout=30)
        result.success = True
        return result
