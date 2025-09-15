"""
NVMe Device Handler

Handles NVMe specific operations including NVMe Format and Sanitize commands.
"""

import os
import time
import logging
import subprocess
import re
from typing import Dict, Any, Optional

from .storage import StorageDevice

logger = logging.getLogger(__name__)


class NVMeDevice:
    """Handler for NVMe devices."""

    def __init__(self):
        """Initialize NVMe device handler."""
        pass

    def prepare_for_wipe(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Prepare NVMe device for wiping.

        Args:
            device: NVMe storage device

        Returns:
            Preparation result dictionary
        """
        result = {
            'success': False,
            'warnings': [],
            'actions_taken': [],
            'capabilities': None
        }

        try:
            # Get device capabilities
            capabilities = self._get_device_capabilities(device.path)
            result['capabilities'] = capabilities

            if not capabilities.get('format_supported', False) and not capabilities.get('sanitize_supported', False):
                result['warnings'].append('Device does not support NVMe Format or Sanitize commands')

            if capabilities.get('crypto_erase_supported', False):
                result['actions_taken'].append('Cryptographic erase capability detected')

            result['success'] = True

        except Exception as e:
            logger.error(f"Failed to prepare NVMe device {device.path}: {e}")

        return result

    def format_secure(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Perform NVMe secure format operation.

        Args:
            device: NVMe storage device

        Returns:
            Format result dictionary
        """
        result = {
            'success': False,
            'method_used': 'nvme_format_secure',
            'duration_seconds': 0,
            'error': None
        }

        start_time = time.time()

        try:
            logger.info(f"Starting NVMe secure format on {device.path}")

            # Use secure erase setting 1 (User Data Erase)
            cmd = ['nvme', 'format', device.path, '--ses=1']
            result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1 hour timeout

            if result_proc.returncode == 0:
                result['success'] = True
                logger.info(f"NVMe secure format completed for {device.path}")
            else:
                result['error'] = f'NVMe format failed: {result_proc.stderr}'
                logger.error(f"NVMe format failed for {device.path}: {result_proc.stderr}")

            result['duration_seconds'] = int(time.time() - start_time)

        except subprocess.TimeoutExpired:
            result['error'] = 'NVMe format operation timed out'
            logger.error(f"NVMe format timed out for {device.path}")

        except Exception as e:
            result['error'] = f'NVMe format failed: {str(e)}'
            logger.error(f"NVMe format failed for {device.path}: {e}")

        return result

    def sanitize(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Perform NVMe sanitize operation.

        Args:
            device: NVMe storage device

        Returns:
            Sanitize result dictionary
        """
        result = {
            'success': False,
            'method_used': 'nvme_sanitize',
            'duration_seconds': 0,
            'error': None
        }

        start_time = time.time()

        try:
            logger.info(f"Starting NVMe sanitize on {device.path}")

            # Try block erase sanitize first (fastest)
            cmd = ['nvme', 'sanitize', device.path, '--sanact=2']  # Block Erase
            result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2 hour timeout

            if result_proc.returncode == 0:
                # Monitor sanitize progress
                if self._wait_for_sanitize_completion(device.path):
                    result['success'] = True
                    result['method_used'] = 'nvme_sanitize_block_erase'
                    logger.info(f"NVMe block erase sanitize completed for {device.path}")
                else:
                    result['error'] = 'Sanitize operation did not complete properly'

            else:
                # Try overwrite sanitize as fallback
                logger.info("Block erase sanitize failed, trying overwrite sanitize")
                cmd = ['nvme', 'sanitize', device.path, '--sanact=3']  # Overwrite
                result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

                if result_proc.returncode == 0:
                    if self._wait_for_sanitize_completion(device.path):
                        result['success'] = True
                        result['method_used'] = 'nvme_sanitize_overwrite'
                        logger.info(f"NVMe overwrite sanitize completed for {device.path}")
                    else:
                        result['error'] = 'Sanitize operation did not complete properly'
                else:
                    result['error'] = f'NVMe sanitize failed: {result_proc.stderr}'
                    logger.error(f"NVMe sanitize failed for {device.path}: {result_proc.stderr}")

            result['duration_seconds'] = int(time.time() - start_time)

        except subprocess.TimeoutExpired:
            result['error'] = 'NVMe sanitize operation timed out'
            logger.error(f"NVMe sanitize timed out for {device.path}")

        except Exception as e:
            result['error'] = f'NVMe sanitize failed: {str(e)}'
            logger.error(f"NVMe sanitize failed for {device.path}: {e}")

        return result

    def get_temperature(self, device: StorageDevice) -> Optional[int]:
        """
        Get NVMe device temperature.

        Args:
            device: NVMe storage device

        Returns:
            Temperature in Celsius or None
        """
        try:
            cmd = ['nvme', 'smart-log', device.path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse temperature from SMART log
                temp_match = re.search(r'temperature\s*:\s*(\d+)', result.stdout, re.IGNORECASE)
                if temp_match:
                    # NVMe temperatures are in Kelvin, convert to Celsius
                    kelvin = int(temp_match.group(1))
                    celsius = kelvin - 273
                    return celsius if celsius > 0 else None

        except Exception as e:
            logger.debug(f"Failed to get NVMe temperature for {device.path}: {e}")

        return None

    def get_smart_data(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Get NVMe SMART data.

        Args:
            device: NVMe storage device

        Returns:
            SMART data dictionary
        """
        smart_data = {}

        try:
            cmd = ['nvme', 'smart-log', device.path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Parse various SMART attributes
                patterns = {
                    'critical_warning': r'critical_warning\s*:\s*(\d+)',
                    'temperature': r'temperature\s*:\s*(\d+)',
                    'available_spare': r'available_spare\s*:\s*(\d+)%',
                    'available_spare_threshold': r'available_spare_threshold\s*:\s*(\d+)%',
                    'percentage_used': r'percentage_used\s*:\s*(\d+)%',
                    'data_units_read': r'data_units_read\s*:\s*(\d+)',
                    'data_units_written': r'data_units_written\s*:\s*(\d+)',
                    'host_read_commands': r'host_read_commands\s*:\s*(\d+)',
                    'host_write_commands': r'host_write_commands\s*:\s*(\d+)',
                    'controller_busy_time': r'controller_busy_time\s*:\s*(\d+)',
                    'power_cycles': r'power_cycles\s*:\s*(\d+)',
                    'power_on_hours': r'power_on_hours\s*:\s*(\d+)',
                }

                for key, pattern in patterns.items():
                    match = re.search(pattern, output, re.IGNORECASE)
                    if match:
                        value = int(match.group(1))
                        if key == 'temperature':
                            # Convert Kelvin to Celsius
                            value = value - 273 if value > 273 else value
                        smart_data[key] = value

        except Exception as e:
            logger.debug(f"Failed to get NVMe SMART data for {device.path}: {e}")

        return smart_data

    def _get_device_capabilities(self, device_path: str) -> Dict[str, Any]:
        """Get NVMe device capabilities."""
        capabilities = {
            'format_supported': False,
            'sanitize_supported': False,
            'crypto_erase_supported': False,
            'block_erase_supported': False,
            'overwrite_supported': False
        }

        try:
            cmd = ['nvme', 'id-ctrl', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Check format capabilities
                if 'Format NVM Supported' in output:
                    capabilities['format_supported'] = True

                # Check sanitize capabilities
                if 'Sanitize' in output:
                    capabilities['sanitize_supported'] = True

                if 'Crypto Erase' in output:
                    capabilities['crypto_erase_supported'] = True

                if 'Block Erase' in output:
                    capabilities['block_erase_supported'] = True

                if 'Overwrite' in output:
                    capabilities['overwrite_supported'] = True

        except Exception as e:
            logger.debug(f"Failed to get NVMe capabilities for {device_path}: {e}")

        return capabilities

    def _wait_for_sanitize_completion(self, device_path: str, timeout_minutes: int = 120) -> bool:
        """
        Wait for NVMe sanitize operation to complete.

        Args:
            device_path: Path to NVMe device
            timeout_minutes: Maximum time to wait

        Returns:
            True if sanitize completed successfully
        """
        timeout_seconds = timeout_minutes * 60
        start_time = time.time()
        check_interval = 30  # Check every 30 seconds

        logger.info(f"Monitoring NVMe sanitize progress for {device_path}")

        while time.time() - start_time < timeout_seconds:
            try:
                cmd = ['nvme', 'sanitize-log', device_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    output = result.stdout

                    # Check sanitize status
                    if 'Sanitize Status' in output:
                        # Look for completion indicators
                        if 'No sanitize operation' in output or 'completed successfully' in output.lower():
                            logger.info("NVMe sanitize operation completed successfully")
                            return True

                        if 'failed' in output.lower() or 'error' in output.lower():
                            logger.error("NVMe sanitize operation failed")
                            return False

                        # Parse progress if available
                        progress_match = re.search(r'progress\s*:\s*(\d+)%', output, re.IGNORECASE)
                        if progress_match:
                            progress = int(progress_match.group(1))
                            logger.info(f"NVMe sanitize progress: {progress}%")

                time.sleep(check_interval)

            except Exception as e:
                logger.debug(f"Error checking sanitize status: {e}")
                time.sleep(check_interval)

        logger.error(f"NVMe sanitize timed out after {timeout_minutes} minutes")
        return False

    def check_sanitize_capability(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Check device's sanitize capabilities.

        Args:
            device: NVMe storage device

        Returns:
            Capability information dictionary
        """
        capabilities = {
            'format_supported': False,
            'sanitize_supported': False,
            'crypto_erase_supported': False,
            'currently_available': False,
            'estimated_time_minutes': 0,
            'blocking_factors': []
        }

        try:
            device_caps = self._get_device_capabilities(device.path)
            capabilities.update(device_caps)

            # Estimate time based on capacity and method
            capacity_gb = device.capacity_bytes / (1024 * 1024 * 1024)

            if capabilities['crypto_erase_supported']:
                # Crypto erase is very fast
                capabilities['estimated_time_minutes'] = 1
            elif capabilities['block_erase_supported']:
                # Block erase is fast
                capabilities['estimated_time_minutes'] = max(5, int(capacity_gb / 100))  # ~1 minute per 100GB
            elif capabilities['format_supported']:
                # Format is moderately fast
                capabilities['estimated_time_minutes'] = max(10, int(capacity_gb / 50))  # ~1 minute per 50GB
            else:
                capabilities['estimated_time_minutes'] = 0

            # Check blocking factors
            if device.is_mounted:
                capabilities['blocking_factors'].append('Device mounted')

            capabilities['currently_available'] = (
                (capabilities['format_supported'] or capabilities['sanitize_supported']) and
                len(capabilities['blocking_factors']) == 0
            )

        except Exception as e:
            logger.error(f"Failed to check sanitize capability for {device.path}: {e}")

        return capabilities

    def list_namespaces(self, device_path: str) -> List[str]:
        """
        List NVMe namespaces for a controller.

        Args:
            device_path: Path to NVMe controller

        Returns:
            List of namespace paths
        """
        namespaces = []

        try:
            cmd = ['nvme', 'list-ns', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip() and line.startswith('['):
                        # Extract namespace number
                        ns_match = re.search(r'\[(\d+)\]', line)
                        if ns_match:
                            ns_num = ns_match.group(1)
                            ns_path = f"{device_path}n{ns_num}"
                            namespaces.append(ns_path)

        except Exception as e:
            logger.debug(f"Failed to list namespaces for {device_path}: {e}")

        return namespaces