"""
Device Handler Module

Manages device-specific operations and hardware-level secure erase commands.
"""

import os
import logging
import subprocess
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

from .storage import StorageDevice, DeviceType, DeviceInterface
from .ata import ATADevice
from .nvme import NVMeDevice

logger = logging.getLogger(__name__)


class DeviceHandler:
    """Main handler for device operations."""

    def __init__(self):
        """Initialize device handler."""
        self.ata_handler = ATADevice()
        self.nvme_handler = NVMeDevice()

    def prepare_device_for_wipe(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Prepare device for wiping operation.

        Args:
            device: Storage device to prepare

        Returns:
            Dictionary with preparation results and warnings
        """
        result = {
            'success': False,
            'warnings': [],
            'errors': [],
            'actions_taken': [],
            'device_ready': False
        }

        try:
            # Check if device is mounted and unmount if needed
            if device.is_mounted:
                unmount_result = self._unmount_device(device)
                result['actions_taken'].append('Device unmounted')
                if not unmount_result:
                    result['errors'].append('Failed to unmount device')
                    return result

            # Check system disk warning
            if device.is_system_disk:
                result['warnings'].append('WARNING: This appears to be a system disk')

            # Device-specific preparations
            if device.interface == DeviceInterface.SATA:
                prep_result = self.ata_handler.prepare_for_wipe(device)
                result['warnings'].extend(prep_result.get('warnings', []))
                result['actions_taken'].extend(prep_result.get('actions_taken', []))

            elif device.interface == DeviceInterface.NVME:
                prep_result = self.nvme_handler.prepare_for_wipe(device)
                result['warnings'].extend(prep_result.get('warnings', []))
                result['actions_taken'].extend(prep_result.get('actions_taken', []))

            result['success'] = True
            result['device_ready'] = True

        except Exception as e:
            result['errors'].append(f'Device preparation failed: {str(e)}')
            logger.error(f"Failed to prepare device {device.path}: {e}")

        return result

    def perform_hardware_erase(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Perform hardware-level secure erase if supported.

        Args:
            device: Storage device to erase

        Returns:
            Dictionary with erase results
        """
        result = {
            'success': False,
            'method_used': None,
            'duration_seconds': 0,
            'error': None
        }

        if not device.supports_hardware_erase:
            result['error'] = 'Device does not support hardware-level secure erase'
            return result

        try:
            if device.interface == DeviceInterface.SATA and device.secure_erase_support:
                result = self.ata_handler.secure_erase(device)

            elif device.interface == DeviceInterface.NVME:
                if device.sanitize_support:
                    result = self.nvme_handler.sanitize(device)
                elif device.secure_erase_support:
                    result = self.nvme_handler.format_secure(device)

        except Exception as e:
            result['error'] = f'Hardware erase failed: {str(e)}'
            logger.error(f"Hardware erase failed for {device.path}: {e}")

        return result

    def get_device_temperature(self, device: StorageDevice) -> Optional[int]:
        """
        Get current device temperature.

        Args:
            device: Storage device

        Returns:
            Temperature in Celsius or None if unavailable
        """
        try:
            if device.interface == DeviceInterface.SATA:
                return self.ata_handler.get_temperature(device)
            elif device.interface == DeviceInterface.NVME:
                return self.nvme_handler.get_temperature(device)

        except Exception as e:
            logger.debug(f"Failed to get temperature for {device.path}: {e}")

        return None

    def monitor_device_health(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Monitor device health during operations.

        Args:
            device: Storage device to monitor

        Returns:
            Health monitoring data
        """
        health_data = {
            'temperature_celsius': None,
            'smart_status': 'unknown',
            'power_on_hours': None,
            'health_percentage': None,
            'warnings': []
        }

        try:
            temperature = self.get_device_temperature(device)
            if temperature:
                health_data['temperature_celsius'] = temperature
                if temperature > 70:
                    health_data['warnings'].append(f'High temperature: {temperature}°C')

            # Get SMART data
            smart_data = self._get_smart_data(device)
            if smart_data:
                health_data.update(smart_data)

        except Exception as e:
            logger.debug(f"Health monitoring failed for {device.path}: {e}")

        return health_data

    def _unmount_device(self, device: StorageDevice) -> bool:
        """Unmount all partitions on device."""
        try:
            device_name = os.path.basename(device.path)

            # Find all mounted partitions
            cmd = ['mount']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return False

            partitions_to_unmount = []
            for line in result.stdout.split('\n'):
                if device_name in line:
                    parts = line.split()
                    if len(parts) >= 1:
                        partitions_to_unmount.append(parts[0])

            # Unmount each partition
            for partition in partitions_to_unmount:
                logger.info(f"Unmounting {partition}")
                cmd = ['umount', partition]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    # Try force unmount
                    cmd = ['umount', '-f', partition]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                    if result.returncode != 0:
                        logger.warning(f"Failed to unmount {partition}")
                        return False

            return True

        except Exception as e:
            logger.error(f"Error unmounting device {device.path}: {e}")
            return False

    def _get_smart_data(self, device: StorageDevice) -> Dict[str, Any]:
        """Get SMART monitoring data."""
        smart_data = {}

        try:
            cmd = ['smartctl', '-A', device.path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Parse power-on hours
                import re
                hours_match = re.search(r'Power_On_Hours\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+)', output)
                if hours_match:
                    smart_data['power_on_hours'] = int(hours_match.group(1))

                # Determine overall health
                if 'PASSED' in output:
                    smart_data['smart_status'] = 'passed'
                elif 'FAILED' in output:
                    smart_data['smart_status'] = 'failed'

        except Exception as e:
            logger.debug(f"Failed to get SMART data for {device.path}: {e}")

        return smart_data

    def check_write_permissions(self, device_path: str) -> bool:
        """Check if we have write permissions to device."""
        try:
            return os.access(device_path, os.W_OK)
        except Exception:
            return False

    def estimate_hardware_erase_time(self, device: StorageDevice) -> int:
        """
        Estimate time for hardware-level erase.

        Args:
            device: Storage device

        Returns:
            Estimated time in seconds
        """
        if not device.supports_hardware_erase:
            return 0

        # Hardware erase times are typically much faster than overwrite methods
        base_times = {
            DeviceType.SSD_SATA: 30,    # 30 seconds for SATA SSD
            DeviceType.SSD_NVME: 10,    # 10 seconds for NVMe SSD
            DeviceType.HDD: 7200,       # 2 hours for large HDD
        }

        base_time = base_times.get(device.device_type, 300)  # 5 minutes default

        # Adjust based on capacity
        capacity_gb = device.capacity_bytes / (1024 * 1024 * 1024)
        if capacity_gb > 1000:  # > 1TB
            base_time *= 2
        elif capacity_gb < 100:  # < 100GB
            base_time //= 2

        return base_time

    def supports_concurrent_operations(self, devices: List[StorageDevice]) -> bool:
        """Check if multiple devices can be wiped concurrently."""
        # Generally safe to wipe multiple devices simultaneously
        # unless they're on the same bus or controller

        device_controllers = set()
        for device in devices:
            # Extract controller information from device path
            controller = device.path[:device.path.rfind('n')] if 'nvme' in device.path else device.path[:-1]
            device_controllers.add(controller)

        # If devices are on different controllers, concurrent operations are safe
        return len(device_controllers) == len(devices)