"""
Device Detection Module

Detects and identifies storage devices on the system.
Uses various Linux tools and interfaces to gather device information.
"""

import os
import re
import logging
import subprocess
from typing import List, Dict, Optional, Any
from pathlib import Path

from .storage import StorageDevice, DeviceType, DeviceInterface

logger = logging.getLogger(__name__)


class DeviceDetector:
    """Detects and identifies storage devices on the system."""

    def __init__(self):
        """Initialize device detector."""
        self.sys_block_path = Path("/sys/block")
        self.dev_path = Path("/dev")

    def list_devices(self) -> List[StorageDevice]:
        """
        List all available storage devices.

        Returns:
            List of StorageDevice objects
        """
        devices = []

        try:
            # Get block devices from /sys/block
            if self.sys_block_path.exists():
                for block_device in self.sys_block_path.iterdir():
                    if block_device.is_dir():
                        device_name = block_device.name

                        # Skip loop devices, ram disks, and other virtual devices
                        if self._should_skip_device(device_name):
                            continue

                        device_path = f"/dev/{device_name}"
                        if Path(device_path).exists():
                            try:
                                device = self._probe_device(device_path)
                                if device:
                                    devices.append(device)
                            except Exception as e:
                                logger.warning(f"Failed to probe device {device_path}: {e}")

        except Exception as e:
            logger.error(f"Error listing devices: {e}")

        return devices

    def get_device_info(self, device_path: str) -> Optional[StorageDevice]:
        """
        Get detailed information about a specific device.

        Args:
            device_path: Path to device (e.g., /dev/sda)

        Returns:
            StorageDevice object or None if device not found
        """
        try:
            return self._probe_device(device_path)
        except Exception as e:
            logger.error(f"Failed to get info for device {device_path}: {e}")
            return None

    def _should_skip_device(self, device_name: str) -> bool:
        """Check if device should be skipped."""
        skip_patterns = [
            r'^loop\d+$',      # Loop devices
            r'^ram\d+$',       # RAM disks
            r'^zram\d+$',      # Compressed RAM
            r'^dm-\d+$',       # Device mapper
            r'^md\d+$',        # Software RAID
            r'^sr\d+$',        # CD/DVD drives
            r'^\d+:\d+$',      # Partition numbers
        ]

        for pattern in skip_patterns:
            if re.match(pattern, device_name):
                return True

        return False

    def _probe_device(self, device_path: str) -> Optional[StorageDevice]:
        """
        Probe a device to get its information.

        Args:
            device_path: Path to device

        Returns:
            StorageDevice object or None
        """
        device_name = os.path.basename(device_path)

        # Get basic device information
        device_info = {
            'path': device_path,
            'model': 'Unknown',
            'serial': 'Unknown',
            'capacity_bytes': 0,
            'device_type': DeviceType.UNKNOWN,
            'interface': DeviceInterface.UNKNOWN,
        }

        # Update with information from various sources
        self._update_from_sysfs(device_info, device_name)
        self._update_from_lsblk(device_info, device_name)
        self._update_from_hdparm(device_info, device_path)
        self._update_from_smartctl(device_info, device_path)
        self._update_from_nvme(device_info, device_path)
        self._update_mount_status(device_info, device_path)
        self._detect_hidden_areas(device_info, device_path)

        # Create StorageDevice object
        try:
            return StorageDevice(**device_info)
        except Exception as e:
            logger.error(f"Failed to create StorageDevice for {device_path}: {e}")
            return None

    def _update_from_sysfs(self, device_info: Dict[str, Any], device_name: str):
        """Update device info from sysfs."""
        try:
            sys_device_path = self.sys_block_path / device_name

            # Get capacity - total physical sectors
            size_file = sys_device_path / "size"
            if size_file.exists():
                sectors = int(size_file.read_text().strip())
                device_info['capacity_bytes'] = sectors * 512  # Standard 512 byte sectors
                device_info['total_sectors'] = sectors

            # Get logical block size and physical block size
            logical_block_size_file = sys_device_path / "queue" / "logical_block_size"
            if logical_block_size_file.exists():
                device_info['logical_block_size'] = int(logical_block_size_file.read_text().strip())

            physical_block_size_file = sys_device_path / "queue" / "physical_block_size"
            if physical_block_size_file.exists():
                device_info['physical_block_size'] = int(physical_block_size_file.read_text().strip())

            # Check if rotational
            rotational_file = sys_device_path / "queue" / "rotational"
            if rotational_file.exists():
                device_info['rotational'] = bool(int(rotational_file.read_text().strip()))

            # Get queue depth
            nr_requests_file = sys_device_path / "queue" / "nr_requests"
            if nr_requests_file.exists():
                device_info['queue_depth'] = int(nr_requests_file.read_text().strip())

            # Check if removable
            removable_file = sys_device_path / "removable"
            if removable_file.exists():
                is_removable = bool(int(removable_file.read_text().strip()))
                if is_removable:
                    device_info['device_type'] = DeviceType.USB_FLASH

        except Exception as e:
            logger.debug(f"Error reading sysfs for {device_name}: {e}")

    def _update_from_lsblk(self, device_info: Dict[str, Any], device_name: str):
        """Update device info from lsblk command."""
        try:
            cmd = ['lsblk', '-n', '-o', 'NAME,MODEL,SERIAL,SIZE,TRAN,TYPE', f'/dev/{device_name}']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 6 and parts[0] == device_name:
                        device_info['model'] = parts[1] if parts[1] != '' else device_info['model']
                        device_info['serial'] = parts[2] if parts[2] != '' else device_info['serial']

                        # Parse transport type
                        transport = parts[4] if len(parts) > 4 else ''
                        if transport == 'sata':
                            device_info['interface'] = DeviceInterface.SATA
                        elif transport == 'usb':
                            device_info['interface'] = DeviceInterface.USB
                        elif transport == 'nvme':
                            device_info['interface'] = DeviceInterface.NVME
                        elif transport == 'scsi':
                            device_info['interface'] = DeviceInterface.SCSI

        except Exception as e:
            logger.debug(f"Error running lsblk for {device_name}: {e}")

    def _update_from_hdparm(self, device_info: Dict[str, Any], device_path: str):
        """Update device info from hdparm command."""
        try:
            cmd = ['hdparm', '-I', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Extract model
                model_match = re.search(r'Model Number:\s+(.+)', output)
                if model_match:
                    device_info['model'] = model_match.group(1).strip()

                # Extract serial
                serial_match = re.search(r'Serial Number:\s+(.+)', output)
                if serial_match:
                    device_info['serial'] = serial_match.group(1).strip()

                # Extract firmware version
                fw_match = re.search(r'Firmware Revision:\s+(.+)', output)
                if fw_match:
                    device_info['firmware_version'] = fw_match.group(1).strip()

                # Check for SSD indicators
                if 'SSD' in output or 'Solid State' in output:
                    device_info['device_type'] = DeviceType.SSD_SATA
                    device_info['rotational'] = False

                # Check secure erase support
                if 'Security:' in output and 'supported' in output:
                    device_info['secure_erase_support'] = True

        except Exception as e:
            logger.debug(f"Error running hdparm for {device_path}: {e}")

    def _update_from_smartctl(self, device_info: Dict[str, Any], device_path: str):
        """Update device info from smartctl command."""
        try:
            cmd = ['smartctl', '-i', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Extract vendor
                vendor_match = re.search(r'Vendor:\s+(.+)', output)
                if vendor_match:
                    device_info['vendor'] = vendor_match.group(1).strip()

                # Extract model (may be more accurate than hdparm)
                model_match = re.search(r'Device Model:\s+(.+)', output)
                if model_match:
                    device_info['model'] = model_match.group(1).strip()

                # Extract serial
                serial_match = re.search(r'Serial Number:\s+(.+)', output)
                if serial_match:
                    device_info['serial'] = serial_match.group(1).strip()

                # Check device type
                if 'SSD' in output or 'Solid State' in output:
                    device_info['device_type'] = DeviceType.SSD_SATA
                    device_info['rotational'] = False
                elif 'NVMe' in output:
                    device_info['device_type'] = DeviceType.SSD_NVME
                    device_info['interface'] = DeviceInterface.NVME
                    device_info['rotational'] = False

            # Get temperature and health status
            cmd = ['smartctl', '-A', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                output = result.stdout

                # Extract temperature
                temp_match = re.search(r'Temperature_Celsius\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+)', output)
                if temp_match:
                    device_info['temperature_celsius'] = int(temp_match.group(1))

                # Check overall health
                device_info['smart_health_ok'] = 'PASSED' in output

        except Exception as e:
            logger.debug(f"Error running smartctl for {device_path}: {e}")

    def _update_from_nvme(self, device_info: Dict[str, Any], device_path: str):
        """Update device info for NVMe devices."""
        if not device_path.startswith('/dev/nvme'):
            return

        try:
            cmd = ['nvme', 'id-ctrl', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Extract model
                model_match = re.search(r'mn\s+:\s+(.+)', output)
                if model_match:
                    device_info['model'] = model_match.group(1).strip()

                # Extract serial
                serial_match = re.search(r'sn\s+:\s+(.+)', output)
                if serial_match:
                    device_info['serial'] = serial_match.group(1).strip()

                # Extract firmware
                fw_match = re.search(r'fr\s+:\s+(.+)', output)
                if fw_match:
                    device_info['firmware_version'] = fw_match.group(1).strip()

                # NVMe devices are SSDs
                device_info['device_type'] = DeviceType.SSD_NVME
                device_info['interface'] = DeviceInterface.NVME
                device_info['rotational'] = False

                # Check for sanitize support
                if 'Format NVM Supported' in output:
                    device_info['secure_erase_support'] = True

                # Check for crypto erase
                if 'Crypto Erase Supported' in output:
                    device_info['sanitize_support'] = True

        except Exception as e:
            logger.debug(f"Error running nvme command for {device_path}: {e}")

    def _update_mount_status(self, device_info: Dict[str, Any], device_path: str):
        """Update mount status and system disk detection."""
        try:
            # Check if any partition of this device is mounted
            mount_points = []
            device_name = os.path.basename(device_path)

            # Check mount command output
            cmd = ['mount']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if device_name in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            mount_points.append(parts[2])

            device_info['mount_points'] = mount_points
            device_info['is_mounted'] = len(mount_points) > 0

            # Check if this is a system disk
            system_mount_points = ['/', '/boot', '/usr', '/var']
            device_info['is_system_disk'] = any(
                mount_point in system_mount_points for mount_point in mount_points
            )

        except Exception as e:
            logger.debug(f"Error checking mount status for {device_path}: {e}")

    def detect_device_capabilities(self, device: StorageDevice) -> StorageDevice:
        """
        Detect advanced capabilities of a device.

        Args:
            device: StorageDevice to update

        Returns:
            Updated StorageDevice
        """
        if device.interface == DeviceInterface.SATA:
            device.secure_erase_support = self._check_ata_secure_erase(device.path)

        elif device.interface == DeviceInterface.NVME:
            capabilities = self._check_nvme_capabilities(device.path)
            device.secure_erase_support = capabilities.get('format_support', False)
            device.sanitize_support = capabilities.get('sanitize_support', False)

        # Check TRIM support for SSDs
        if device.device_type in [DeviceType.SSD_SATA, DeviceType.SSD_NVME]:
            device.trim_support = self._check_trim_support(device.path)

        return device

    def _check_ata_secure_erase(self, device_path: str) -> bool:
        """Check if ATA Secure Erase is supported."""
        try:
            cmd = ['hdparm', '-I', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                return 'Security:' in result.stdout and 'supported' in result.stdout

        except Exception as e:
            logger.debug(f"Error checking ATA secure erase for {device_path}: {e}")

        return False

    def _check_nvme_capabilities(self, device_path: str) -> Dict[str, bool]:
        """Check NVMe device capabilities."""
        capabilities = {
            'format_support': False,
            'sanitize_support': False,
            'crypto_erase_support': False
        }

        try:
            cmd = ['nvme', 'id-ctrl', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout
                capabilities['format_support'] = 'Format NVM Supported' in output
                capabilities['sanitize_support'] = 'Sanitize' in output
                capabilities['crypto_erase_support'] = 'Crypto Erase' in output

        except Exception as e:
            logger.debug(f"Error checking NVMe capabilities for {device_path}: {e}")

        return capabilities

    def _check_trim_support(self, device_path: str) -> bool:
        """Check if device supports TRIM/DISCARD commands."""
        try:
            device_name = os.path.basename(device_path)
            discard_file = self.sys_block_path / device_name / "queue" / "discard_granularity"

            if discard_file.exists():
                granularity = int(discard_file.read_text().strip())
                return granularity > 0

        except Exception as e:
            logger.debug(f"Error checking TRIM support for {device_path}: {e}")

        return False

    def _detect_hidden_areas(self, device_info: Dict[str, Any], device_path: str):
        """Detect hidden areas like HPA (Host Protected Area) and DCO (Device Configuration Overlay)."""
        try:
            device_info['hpa_detected'] = False
            device_info['dco_detected'] = False
            device_info['hidden_sectors'] = 0
            device_info['native_max_sectors'] = device_info.get('total_sectors', 0)

            # Check for HPA using hdparm
            self._check_hpa_with_hdparm(device_info, device_path)

            # Check for additional hidden areas using smartctl
            self._check_hidden_with_smartctl(device_info, device_path)

            # Calculate total hidden capacity
            total_sectors = device_info.get('total_sectors', 0)
            native_max = device_info.get('native_max_sectors', 0)

            if native_max > total_sectors:
                device_info['hidden_sectors'] = native_max - total_sectors
                device_info['hidden_capacity_bytes'] = device_info['hidden_sectors'] * 512
            else:
                device_info['hidden_capacity_bytes'] = 0

            # Add descriptive capacity breakdown
            self._add_capacity_breakdown(device_info)

        except Exception as e:
            logger.debug(f"Error detecting hidden areas for {device_path}: {e}")

    def _check_hpa_with_hdparm(self, device_info: Dict[str, Any], device_path: str):
        """Check for Host Protected Area using hdparm."""
        try:
            cmd = ['hdparm', '-N', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                output = result.stdout

                # Look for HPA information
                for line in output.split('\n'):
                    if 'max sectors' in line.lower():
                        # Extract current and native max sectors
                        parts = line.split(',')
                        for part in parts:
                            if 'HPA' in part and 'is enabled' in part:
                                device_info['hpa_detected'] = True
                            elif 'native max' in part.lower():
                                # Try to extract native max sectors
                                numbers = re.findall(r'\d+', part)
                                if numbers:
                                    device_info['native_max_sectors'] = int(numbers[-1])

        except Exception as e:
            logger.debug(f"Error checking HPA with hdparm for {device_path}: {e}")

    def _check_hidden_with_smartctl(self, device_info: Dict[str, Any], device_path: str):
        """Check for hidden areas using smartctl."""
        try:
            cmd = ['smartctl', '-i', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                output = result.stdout

                # Look for total LBA sectors vs user addressable sectors
                user_capacity_match = re.search(r'User Capacity:\s*([0-9,]+)\s*bytes', output)
                device_size_match = re.search(r'Device size with M = 1000\*1000:\s*([0-9,]+)', output)

                if user_capacity_match:
                    user_capacity_str = user_capacity_match.group(1).replace(',', '')
                    user_capacity = int(user_capacity_str)
                    device_info['user_capacity_bytes'] = user_capacity

                    # Compare with total capacity to detect hidden areas
                    total_capacity = device_info.get('capacity_bytes', 0)
                    if total_capacity > user_capacity:
                        device_info['hidden_capacity_bytes'] = total_capacity - user_capacity
                        device_info['hidden_sectors'] = device_info['hidden_capacity_bytes'] // 512

        except Exception as e:
            logger.debug(f"Error checking hidden areas with smartctl for {device_path}: {e}")

    def _add_capacity_breakdown(self, device_info: Dict[str, Any]):
        """Add human-readable capacity breakdown information."""
        def format_bytes(bytes_val):
            if bytes_val == 0:
                return "0 B"
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} PB"

        total_capacity = device_info.get('capacity_bytes', 0)
        hidden_capacity = device_info.get('hidden_capacity_bytes', 0)
        user_capacity = total_capacity - hidden_capacity

        device_info['capacity_breakdown'] = {
            'total_physical': format_bytes(total_capacity),
            'user_accessible': format_bytes(user_capacity),
            'hidden_areas': format_bytes(hidden_capacity),
            'hidden_percentage': (hidden_capacity / total_capacity * 100) if total_capacity > 0 else 0
        }

        # Update the main capacity_human to show breakdown
        if hidden_capacity > 0:
            device_info['capacity_human'] = f"{format_bytes(total_capacity)} (User: {format_bytes(user_capacity)}, Hidden: {format_bytes(hidden_capacity)})"
        else:
            device_info['capacity_human'] = format_bytes(total_capacity)