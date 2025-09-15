"""
ATA Device Handler

Handles ATA/SATA specific operations including ATA Secure Erase.
"""

import os
import time
import logging
import subprocess
import re
from typing import Dict, Any, Optional

from .storage import StorageDevice

logger = logging.getLogger(__name__)


class ATADevice:
    """Handler for ATA/SATA devices."""

    def __init__(self):
        """Initialize ATA device handler."""
        pass

    def prepare_for_wipe(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Prepare ATA device for wiping.

        Args:
            device: ATA/SATA storage device

        Returns:
            Preparation result dictionary
        """
        result = {
            'success': False,
            'warnings': [],
            'actions_taken': [],
            'security_status': None
        }

        try:
            # Check security status
            security_info = self._get_security_status(device.path)
            result['security_status'] = security_info

            if security_info.get('frozen', False):
                result['warnings'].append('Device security is frozen - hardware secure erase unavailable')

            if security_info.get('locked', False):
                result['warnings'].append('Device is security locked')

            # Disable any power management that might interfere
            self._disable_power_management(device.path)
            result['actions_taken'].append('Power management disabled')

            result['success'] = True

        except Exception as e:
            logger.error(f"Failed to prepare ATA device {device.path}: {e}")

        return result

    def secure_erase(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Perform ATA Secure Erase on device.

        Args:
            device: ATA/SATA storage device

        Returns:
            Secure erase result dictionary
        """
        result = {
            'success': False,
            'method_used': 'ata_secure_erase',
            'duration_seconds': 0,
            'error': None
        }

        start_time = time.time()

        try:
            # Check if secure erase is available
            security_info = self._get_security_status(device.path)

            if not security_info.get('supported', False):
                result['error'] = 'ATA Secure Erase not supported'
                return result

            if security_info.get('frozen', False):
                result['error'] = 'Device security is frozen'
                return result

            # Estimate time for secure erase
            erase_time = security_info.get('erase_time_minutes', 120)  # Default 2 hours
            logger.info(f"Starting ATA Secure Erase on {device.path}, estimated time: {erase_time} minutes")

            # Step 1: Set user password
            password = 'BreakNWipe'
            if not self._set_security_password(device.path, password):
                result['error'] = 'Failed to set security password'
                return result

            # Step 2: Issue secure erase command
            if not self._issue_secure_erase_command(device.path, password):
                result['error'] = 'Failed to issue secure erase command'
                return result

            # Step 3: Wait for completion and monitor
            if not self._wait_for_erase_completion(device.path, erase_time):
                result['error'] = 'Secure erase timed out or failed'
                return result

            result['success'] = True
            result['duration_seconds'] = int(time.time() - start_time)

        except Exception as e:
            result['error'] = f'ATA Secure Erase failed: {str(e)}'
            logger.error(f"ATA Secure Erase failed for {device.path}: {e}")

        return result

    def get_temperature(self, device: StorageDevice) -> Optional[int]:
        """
        Get device temperature using ATA commands.

        Args:
            device: ATA/SATA storage device

        Returns:
            Temperature in Celsius or None
        """
        try:
            cmd = ['smartctl', '-A', device.path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse temperature from SMART attributes
                temp_match = re.search(r'Temperature_Celsius\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+)', result.stdout)
                if temp_match:
                    return int(temp_match.group(1))

        except Exception as e:
            logger.debug(f"Failed to get ATA temperature for {device.path}: {e}")

        return None

    def _get_security_status(self, device_path: str) -> Dict[str, Any]:
        """Get ATA security status."""
        security_info = {
            'supported': False,
            'enabled': False,
            'locked': False,
            'frozen': False,
            'count_expired': False,
            'erase_time_minutes': 0,
            'enhanced_erase_time_minutes': 0
        }

        try:
            cmd = ['hdparm', '-I', device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                output = result.stdout

                # Parse security features
                security_section = False
                for line in output.split('\n'):
                    line = line.strip()

                    if 'Security:' in line:
                        security_section = True
                        continue

                    if security_section:
                        if line.startswith('Master password'):
                            security_section = False
                            continue

                        if 'supported' in line.lower():
                            security_info['supported'] = True

                        if 'enabled' in line.lower():
                            security_info['enabled'] = True

                        if 'locked' in line.lower():
                            security_info['locked'] = True

                        if 'frozen' in line.lower():
                            security_info['frozen'] = True

                        if 'expired' in line.lower():
                            security_info['count_expired'] = True

                        # Parse erase times
                        time_match = re.search(r'(\d+)min for SECURITY ERASE UNIT', line)
                        if time_match:
                            security_info['erase_time_minutes'] = int(time_match.group(1))

                        enhanced_time_match = re.search(r'(\d+)min for ENHANCED SECURITY ERASE UNIT', line)
                        if enhanced_time_match:
                            security_info['enhanced_erase_time_minutes'] = int(enhanced_time_match.group(1))

        except Exception as e:
            logger.debug(f"Failed to get security status for {device_path}: {e}")

        return security_info

    def _set_security_password(self, device_path: str, password: str) -> bool:
        """Set ATA security password."""
        try:
            cmd = ['hdparm', '--user-master', 'u', '--security-set-pass', password, device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                logger.info(f"Security password set for {device_path}")
                return True
            else:
                logger.error(f"Failed to set security password: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error setting security password for {device_path}: {e}")
            return False

    def _issue_secure_erase_command(self, device_path: str, password: str) -> bool:
        """Issue ATA secure erase command."""
        try:
            cmd = ['hdparm', '--user-master', 'u', '--security-erase', password, device_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                logger.info(f"Secure erase command issued for {device_path}")
                return True
            else:
                logger.error(f"Failed to issue secure erase command: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error issuing secure erase command for {device_path}: {e}")
            return False

    def _wait_for_erase_completion(self, device_path: str, timeout_minutes: int) -> bool:
        """Wait for secure erase to complete."""
        timeout_seconds = timeout_minutes * 60 + 300  # Add 5 minute buffer
        start_time = time.time()
        check_interval = 30  # Check every 30 seconds

        logger.info(f"Waiting for secure erase to complete (timeout: {timeout_minutes} minutes)")

        while time.time() - start_time < timeout_seconds:
            try:
                # Check if device is accessible and security status
                security_info = self._get_security_status(device_path)

                # If device is no longer locked/enabled, erase might be complete
                if not security_info.get('enabled', True):
                    logger.info("Device security disabled - erase appears complete")
                    return True

                # Sleep before next check
                time.sleep(check_interval)

            except Exception as e:
                logger.debug(f"Error checking erase status: {e}")
                time.sleep(check_interval)

        logger.error(f"Secure erase timed out after {timeout_minutes} minutes")
        return False

    def _disable_power_management(self, device_path: str):
        """Disable power management features that might interfere with secure erase."""
        try:
            # Disable APM (Advanced Power Management)
            cmd = ['hdparm', '-B', '255', device_path]
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            # Disable standby timer
            cmd = ['hdparm', '-S', '0', device_path]
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            logger.debug(f"Power management disabled for {device_path}")

        except Exception as e:
            logger.debug(f"Error disabling power management for {device_path}: {e}")

    def check_erase_capability(self, device: StorageDevice) -> Dict[str, Any]:
        """
        Check device's secure erase capabilities.

        Args:
            device: ATA/SATA storage device

        Returns:
            Capability information dictionary
        """
        capabilities = {
            'secure_erase_supported': False,
            'enhanced_secure_erase_supported': False,
            'currently_available': False,
            'estimated_time_minutes': 0,
            'blocking_factors': []
        }

        try:
            security_info = self._get_security_status(device.path)

            capabilities['secure_erase_supported'] = security_info.get('supported', False)
            capabilities['estimated_time_minutes'] = security_info.get('erase_time_minutes', 0)

            if security_info.get('enhanced_erase_time_minutes', 0) > 0:
                capabilities['enhanced_secure_erase_supported'] = True

            # Check blocking factors
            if security_info.get('frozen', False):
                capabilities['blocking_factors'].append('Security frozen')

            if security_info.get('locked', False):
                capabilities['blocking_factors'].append('Device locked')

            if device.is_mounted:
                capabilities['blocking_factors'].append('Device mounted')

            capabilities['currently_available'] = (
                capabilities['secure_erase_supported'] and
                len(capabilities['blocking_factors']) == 0
            )

        except Exception as e:
            logger.error(f"Failed to check erase capability for {device.path}: {e}")

        return capabilities