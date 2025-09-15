"""
Storage Device Models

Data models for different types of storage devices.
"""

import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class DeviceType(Enum):
    """Types of storage devices."""
    HDD = "hdd"
    SSD_SATA = "ssd_sata"
    SSD_NVME = "ssd_nvme"
    USB_FLASH = "usb_flash"
    SD_CARD = "sd_card"
    EMMC = "emmc"
    UNKNOWN = "unknown"


class DeviceInterface(Enum):
    """Storage device interfaces."""
    SATA = "sata"
    PATA = "pata"
    NVME = "nvme"
    USB = "usb"
    MMC = "mmc"
    SCSI = "scsi"
    UNKNOWN = "unknown"


@dataclass
class StorageDevice:
    """Represents a storage device with its properties."""

    path: str                           # Device path (e.g., /dev/sda)
    model: str                          # Device model
    serial: str                         # Serial number
    capacity_bytes: int                 # Capacity in bytes
    device_type: DeviceType             # Type of device
    interface: DeviceInterface          # Interface type
    firmware_version: Optional[str] = None

    # Hardware features
    secure_erase_support: bool = False
    sanitize_support: bool = False
    trim_support: bool = False

    # Status information
    is_mounted: bool = False
    mount_points: List[str] = None
    is_system_disk: bool = False

    # Performance characteristics
    rotational: bool = True
    queue_depth: Optional[int] = None
    max_sectors: Optional[int] = None

    # Temperature and health
    temperature_celsius: Optional[int] = None
    smart_health_ok: bool = True

    # Additional metadata
    vendor: Optional[str] = None
    wwn: Optional[str] = None  # World Wide Name
    logical_block_size: int = 512
    physical_block_size: int = 512

    def __post_init__(self):
        """Initialize computed properties."""
        if self.mount_points is None:
            self.mount_points = []

        # Determine if rotational based on device type
        if self.device_type in [DeviceType.SSD_SATA, DeviceType.SSD_NVME,
                               DeviceType.USB_FLASH, DeviceType.SD_CARD, DeviceType.EMMC]:
            self.rotational = False

    @property
    def capacity_human(self) -> str:
        """Human readable capacity."""
        return self._format_bytes(self.capacity_bytes)

    @property
    def device_name(self) -> str:
        """Short device name (e.g., sda)."""
        return os.path.basename(self.path)

    @property
    def is_removable(self) -> bool:
        """Check if device is removable."""
        return self.device_type in [DeviceType.USB_FLASH, DeviceType.SD_CARD]

    @property
    def supports_hardware_erase(self) -> bool:
        """Check if device supports hardware-level secure erase."""
        return self.secure_erase_support or self.sanitize_support

    @property
    def recommended_algorithm(self) -> str:
        """Get recommended wiping algorithm for this device type."""
        if self.device_type == DeviceType.HDD:
            return "nist-purge"  # Multiple passes for HDDs
        elif self.device_type in [DeviceType.SSD_SATA, DeviceType.SSD_NVME]:
            if self.supports_hardware_erase:
                return "hardware"  # Use built-in secure erase
            else:
                return "nist-clear"  # Single pass for SSDs
        else:
            return "nist-clear"  # Default for unknown/other types

    @property
    def wipe_complexity(self) -> str:
        """Get complexity level for wiping this device."""
        if self.device_type == DeviceType.HDD:
            return "medium"  # Magnetic storage, multiple passes needed
        elif self.device_type in [DeviceType.SSD_SATA, DeviceType.SSD_NVME]:
            if self.supports_hardware_erase:
                return "low"     # Hardware erase is fast and simple
            else:
                return "high"    # SSD without hardware erase is complex
        else:
            return "medium"

    def get_wipe_warnings(self) -> List[str]:
        """Get warnings specific to wiping this device."""
        warnings = []

        if self.is_system_disk:
            warnings.append("⚠️  This appears to be a system disk - wiping will make system unbootable")

        if self.is_mounted:
            warnings.append("⚠️  Device is currently mounted - unmount before wiping")

        if self.device_type in [DeviceType.SSD_SATA, DeviceType.SSD_NVME] and not self.supports_hardware_erase:
            warnings.append("⚠️  SSD without hardware erase - data recovery may still be possible")

        if not self.smart_health_ok:
            warnings.append("⚠️  Device reports health issues - wiping may be slow or incomplete")

        if self.temperature_celsius and self.temperature_celsius > 60:
            warnings.append(f"⚠️  Device temperature high ({self.temperature_celsius}°C) - monitor during wipe")

        return warnings

    def get_estimated_wipe_time(self, algorithm_passes: int = 1) -> int:
        """
        Estimate wipe time in seconds.

        Args:
            algorithm_passes: Number of passes the algorithm uses

        Returns:
            Estimated time in seconds
        """
        # Base write speeds in MB/s (conservative estimates)
        speed_estimates = {
            DeviceType.HDD: 80,           # 80 MB/s for HDDs
            DeviceType.SSD_SATA: 200,     # 200 MB/s for SATA SSDs
            DeviceType.SSD_NVME: 800,     # 800 MB/s for NVMe SSDs
            DeviceType.USB_FLASH: 20,     # 20 MB/s for USB flash
            DeviceType.SD_CARD: 15,       # 15 MB/s for SD cards
            DeviceType.EMMC: 40,          # 40 MB/s for eMMC
            DeviceType.UNKNOWN: 50        # Conservative default
        }

        speed_mbps = speed_estimates.get(self.device_type, 50)

        # Hardware erase is much faster
        if self.supports_hardware_erase and algorithm_passes == 1:
            speed_mbps *= 10  # Hardware erase is typically 10x faster

        total_mb = (self.capacity_bytes / (1024 * 1024)) * algorithm_passes
        return int(total_mb / speed_mbps)

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary representation."""
        return {
            'path': self.path,
            'name': self.device_name,
            'model': self.model,
            'serial': self.serial,
            'capacity_bytes': self.capacity_bytes,
            'capacity_human': self.capacity_human,
            'device_type': self.device_type.value,
            'interface': self.interface.value,
            'firmware_version': self.firmware_version,
            'secure_erase_support': self.secure_erase_support,
            'sanitize_support': self.sanitize_support,
            'trim_support': self.trim_support,
            'is_mounted': self.is_mounted,
            'mount_points': self.mount_points,
            'is_system_disk': self.is_system_disk,
            'rotational': self.rotational,
            'temperature_celsius': self.temperature_celsius,
            'smart_health_ok': self.smart_health_ok,
            'vendor': self.vendor,
            'wwn': self.wwn,
            'logical_block_size': self.logical_block_size,
            'physical_block_size': self.physical_block_size,
            'recommended_algorithm': self.recommended_algorithm,
            'wipe_complexity': self.wipe_complexity,
            'warnings': self.get_wipe_warnings()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageDevice':
        """Create StorageDevice from dictionary."""
        device = cls(
            path=data['path'],
            model=data.get('model', 'Unknown'),
            serial=data.get('serial', 'Unknown'),
            capacity_bytes=data.get('capacity_bytes', 0),
            device_type=DeviceType(data.get('device_type', DeviceType.UNKNOWN.value)),
            interface=DeviceInterface(data.get('interface', DeviceInterface.UNKNOWN.value)),
            firmware_version=data.get('firmware_version'),
            secure_erase_support=data.get('secure_erase_support', False),
            sanitize_support=data.get('sanitize_support', False),
            trim_support=data.get('trim_support', False),
            is_mounted=data.get('is_mounted', False),
            mount_points=data.get('mount_points', []),
            is_system_disk=data.get('is_system_disk', False),
            rotational=data.get('rotational', True),
            queue_depth=data.get('queue_depth'),
            max_sectors=data.get('max_sectors'),
            temperature_celsius=data.get('temperature_celsius'),
            smart_health_ok=data.get('smart_health_ok', True),
            vendor=data.get('vendor'),
            wwn=data.get('wwn'),
            logical_block_size=data.get('logical_block_size', 512),
            physical_block_size=data.get('physical_block_size', 512)
        )
        return device

    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes into human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_count < 1024:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024
        return f"{bytes_count:.1f} EB"

    def __str__(self) -> str:
        """String representation of device."""
        return f"{self.device_name} ({self.model}) - {self.capacity_human} {self.device_type.value}"

    def __repr__(self) -> str:
        """Detailed representation of device."""
        return (f"StorageDevice(path='{self.path}', model='{self.model}', "
               f"capacity='{self.capacity_human}', type='{self.device_type.value}')")