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

__all__ = [
    'DeviceDetector',
    'DeviceHandler',
    'StorageDevice',
    'DeviceType',
    'ATADevice',
    'NVMeDevice',
]