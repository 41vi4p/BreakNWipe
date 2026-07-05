"""
Device Handler Module

Device detection, classification, and hardware-specific operations.
Supports HDDs, SSDs, NVMe drives, and various interfaces.
"""

from .detector import DeviceDetector
from .handler import DeviceHandler
from .storage import StorageDevice, DeviceType
from .ata import ATADevice
from .nvme import NVMeDevice
from .filesystem import PartitionInfo, list_partitions, get_filesystem_type, get_mount_point
from .health import DeviceHealth, get_device_health
from .fsck import FilesystemChecker, FsckResult

__all__ = [
    'DeviceDetector',
    'DeviceHandler',
    'StorageDevice',
    'DeviceType',
    'ATADevice',
    'NVMeDevice',
    'PartitionInfo',
    'list_partitions',
    'get_filesystem_type',
    'get_mount_point',
    'DeviceHealth',
    'get_device_health',
    'FilesystemChecker',
    'FsckResult',
]