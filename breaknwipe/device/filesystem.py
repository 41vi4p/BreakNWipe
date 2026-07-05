"""
Filesystem/Partition Inspection Module

Detects partitions, filesystem types, and mount points for a given storage
device. Deliberately kept isolated from the wipe-critical mount-parsing code
in detector.py/handler.py/wipe_engine/engine.py -- those implementations do
substring matching against `mount` output (e.g. "sda1" also matches "sda10"),
which is a harmless over-match for the wipe path (worst case: an extra,
unnecessary unmount attempt) but would be a real safety bug for anything that
needs to know *exactly* whether one specific partition is mounted before
touching its filesystem (fsck). This module always does exact matching
against /proc/mounts instead.
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Filesystem/partition "types" that aren't repairable filesystems in their own
# right -- they're containers (encryption, volume management, RAID) whose
# unlocked/assembled mapped device is the real target, or plain swap space.
UNREPAIRABLE_FSTYPES = {"swap", "crypto_LUKS", "LVM2_member", "linux_raid_member"}

# Mount points that identify a partition as part of the running system, used
# to gate destructive operations (matches the convention already used by
# DeviceDetector._update_mount_status for is_system_disk).
SYSTEM_MOUNT_POINTS = {"/", "/boot", "/boot/efi", "/usr", "/var", "/home"}


@dataclass
class PartitionInfo:
    """A single partition (or the whole disk, if unpartitioned) and its filesystem."""

    path: str                              # e.g. /dev/sda1
    parent_disk: str                       # e.g. /dev/sda
    size_bytes: int = 0
    fstype: Optional[str] = None           # e.g. "ext4", "vfat", "ntfs"; None if none/unknown
    label: Optional[str] = None
    uuid: Optional[str] = None
    mount_point: Optional[str] = None
    is_mounted: bool = False
    is_system: bool = False                # mounted at / , /boot, /usr, /var, /home, ...

    @property
    def size_human(self) -> str:
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} EB"

    @property
    def is_repairable_type(self) -> bool:
        """Whether this partition's fstype is something fsck could conceivably operate on."""
        return self.fstype is not None and self.fstype not in UNREPAIRABLE_FSTYPES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "parent_disk": self.parent_disk,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "fstype": self.fstype,
            "label": self.label,
            "uuid": self.uuid,
            "mount_point": self.mount_point,
            "is_mounted": self.is_mounted,
            "is_system": self.is_system,
            "is_repairable_type": self.is_repairable_type,
        }


def _read_proc_mounts() -> List[Dict[str, str]]:
    """
    Parse /proc/mounts into a list of {device, mount_point, fstype} dicts,
    with exact device paths (no substring matching involved anywhere).
    """
    entries = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                device, mount_point, fstype = parts[0], parts[1], parts[2]
                # /proc/mounts octal-escapes spaces and a few other characters
                # (e.g. "\040" for a literal space) in both fields.
                device = _unescape_octal(device)
                mount_point = _unescape_octal(mount_point)
                entries.append({"device": device, "mount_point": mount_point, "fstype": fstype})
    except (OSError, IOError) as e:
        logger.warning(f"Could not read /proc/mounts: {e}")
    return entries


def _unescape_octal(value: str) -> str:
    """Decode octal escapes (e.g. \\040 -> space) used by /proc/mounts."""
    import re as _re

    return _re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def get_mount_point(partition_path: str) -> Optional[str]:
    """
    Return the exact mount point of partition_path, or None if it isn't
    mounted. Uses /proc/mounts with an exact device-path match -- not a
    substring/grep match -- so "/dev/sda1" can never be confused with
    "/dev/sda10" or vice versa.
    """
    for entry in _read_proc_mounts():
        if entry["device"] == partition_path:
            return entry["mount_point"]
    return None


def is_system_mount_point(mount_point: Optional[str]) -> bool:
    """Whether mount_point identifies this as part of the running system."""
    return mount_point in SYSTEM_MOUNT_POINTS if mount_point else False


def get_filesystem_type(partition_path: str) -> Optional[str]:
    """
    Return the filesystem type of partition_path (e.g. "ext4", "ntfs",
    "vfat"), or None if it has no recognizable filesystem (e.g. it's an
    unpartitioned whole disk, or blkid simply doesn't recognize it).
    """
    try:
        result = subprocess.run(
            ["blkid", "-o", "value", "-s", "TYPE", partition_path],
            capture_output=True, text=True, timeout=10,
        )
        fstype = result.stdout.strip()
        return fstype if fstype else None
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        logger.warning(f"Could not determine filesystem type for {partition_path}: {e}")
        return None


def list_partitions(device_path: str) -> List[PartitionInfo]:
    """
    List all partitions on device_path (e.g. /dev/sda -> /dev/sda1, /dev/sda2, ...),
    each with filesystem type, mount status, and label/uuid where available.
    If the device itself has no partition table but does have a filesystem
    directly on it (common for USB flash drives), a single PartitionInfo for
    the whole device is returned.
    """
    partitions: List[PartitionInfo] = []

    try:
        result = subprocess.run(
            [
                "lsblk", "-J", "-b",
                "-o", "NAME,PATH,SIZE,FSTYPE,MOUNTPOINT,LABEL,UUID,TYPE",
                device_path,
            ],
            capture_output=True, text=True, timeout=15,
        )

        if result.returncode != 0:
            logger.warning(f"lsblk failed for {device_path}: {result.stderr.strip()}")
            return partitions

        data = json.loads(result.stdout)
        block_devices = data.get("blockdevices", [])
        if not block_devices:
            return partitions

        root = block_devices[0]
        children = root.get("children", [])

        # Nodes to turn into PartitionInfo: actual partitions if there are
        # any, otherwise the whole disk itself (e.g. a USB stick formatted
        # without a partition table).
        nodes = children if children else [root]

        for node in nodes:
            node_type = node.get("type", "")
            if node_type not in ("part", "disk", "lvm", "crypt", "loop"):
                continue

            path = node.get("path") or f"/dev/{node.get('name', '')}"
            # Prefer the live, exact mount-point lookup over lsblk's own
            # MOUNTPOINT column, which can be stale/empty depending on the
            # lsblk version -- get_mount_point() is the single source of truth
            # used by the fsck safety gate too, so keep this consistent.
            mount_point = get_mount_point(path) or node.get("mountpoint")

            # Same idea for fstype: lsblk's own FSTYPE column can come back
            # null for some device types (observed with standalone loop
            # devices carrying a real filesystem) even though blkid correctly
            # identifies it -- fall back to the same blkid-based lookup
            # get_filesystem_type() uses, since that's the source of truth
            # the fsck safety gate relies on.
            fstype = node.get("fstype") or get_filesystem_type(path)

            partitions.append(PartitionInfo(
                path=path,
                parent_disk=device_path,
                size_bytes=int(node.get("size") or 0),
                fstype=fstype,
                label=node.get("label"),
                uuid=node.get("uuid"),
                mount_point=mount_point,
                is_mounted=mount_point is not None,
                is_system=is_system_mount_point(mount_point),
            ))

    except (subprocess.SubprocessError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not list partitions for {device_path}: {e}")

    return partitions
