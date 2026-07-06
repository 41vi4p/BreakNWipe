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
from .partition import (
    DiskLayout,
    ResizePlan,
    ResizeResult,
    PartitionResizer,
    get_disk_layout,
    list_logical_volumes,
    extend_lv,
)
from .hexview import SectorData, read_sectors, device_size_bytes
from .recovery import (
    RecoverableFile,
    ScanResult,
    RecoverResult,
    recovery_tools,
    scan_deleted,
    recover_files,
    deep_scan_recover,
)

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
    'DiskLayout',
    'ResizePlan',
    'ResizeResult',
    'PartitionResizer',
    'get_disk_layout',
    'list_logical_volumes',
    'extend_lv',
    'SectorData',
    'read_sectors',
    'device_size_bytes',
    'RecoverableFile',
    'ScanResult',
    'RecoverResult',
    'recovery_tools',
    'scan_deleted',
    'recover_files',
    'deep_scan_recover',
]