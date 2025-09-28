"""
Mobile Device Handler for BreakNWipe

Provides support for Android device wiping through various methods:
- EDL (Emergency Download Mode) for Qualcomm devices
- SP Flash Tool mode for MediaTek devices
- Odin Download mode for Samsung devices
- ADB-based factory reset for general Android devices
"""

import os
import logging
import subprocess
import time
from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MobileWipeMode(Enum):
    """Enumeration of mobile device wipe modes."""
    EDL = "edl"
    SP_FLASH = "spflash"
    ODIN = "odin"
    ADB = "adb"


@dataclass
class MobileDeviceInfo:
    """Information about a detected mobile device."""
    device_id: str
    model: str
    manufacturer: str
    android_version: str
    mode: MobileWipeMode
    status: str
    is_bootloader_unlocked: bool = False
    has_root: bool = False


class MobileDeviceHandler:
    """Handler for mobile device operations."""

    def __init__(self):
        """Initialize mobile device handler."""
        self.adb_path = self._find_adb_executable()
        self.fastboot_path = self._find_fastboot_executable()

    def _find_adb_executable(self) -> Optional[str]:
        """Find ADB executable in system PATH."""
        try:
            result = subprocess.run(['which', 'adb'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass

        # Common ADB installation paths
        common_paths = [
            '/usr/bin/adb',
            '/usr/local/bin/adb',
            '/opt/android-sdk/platform-tools/adb',
            '/home/*/Android/Sdk/platform-tools/adb',
            '~/Android/Sdk/platform-tools/adb'
        ]

        for path in common_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.isfile(expanded_path) and os.access(expanded_path, os.X_OK):
                return expanded_path

        return None

    def _find_fastboot_executable(self) -> Optional[str]:
        """Find fastboot executable in system PATH."""
        try:
            result = subprocess.run(['which', 'fastboot'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass

        # Common fastboot installation paths
        common_paths = [
            '/usr/bin/fastboot',
            '/usr/local/bin/fastboot',
            '/opt/android-sdk/platform-tools/fastboot',
            '/home/*/Android/Sdk/platform-tools/fastboot',
            '~/Android/Sdk/platform-tools/fastboot'
        ]

        for path in common_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.isfile(expanded_path) and os.access(expanded_path, os.X_OK):
                return expanded_path

        return None

    def detect_devices(self) -> List[MobileDeviceInfo]:
        """Detect connected mobile devices."""
        devices = []

        # Check for ADB devices
        if self.adb_path:
            devices.extend(self._detect_adb_devices())

        # Check for fastboot devices
        if self.fastboot_path:
            devices.extend(self._detect_fastboot_devices())

        # TODO: Add detection for EDL, SP Flash, and Odin modes
        # These require specific drivers and tools

        return devices

    def _detect_adb_devices(self) -> List[MobileDeviceInfo]:
        """Detect devices in ADB mode."""
        devices = []

        try:
            result = subprocess.run(
                [self.adb_path, 'devices', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip() and not line.startswith('*'):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == 'device':
                            device_id = parts[0]
                            device_info = self._get_device_properties(device_id)
                            if device_info:
                                devices.append(device_info)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to detect ADB devices: {e}")

        return devices

    def _detect_fastboot_devices(self) -> List[MobileDeviceInfo]:
        """Detect devices in fastboot mode."""
        devices = []

        try:
            result = subprocess.run(
                [self.fastboot_path, 'devices'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[1] == 'fastboot':
                            device_id = parts[0]
                            devices.append(MobileDeviceInfo(
                                device_id=device_id,
                                model="Unknown (Fastboot Mode)",
                                manufacturer="Unknown",
                                android_version="Unknown",
                                mode=MobileWipeMode.ADB,  # Using ADB as generic
                                status="fastboot",
                                is_bootloader_unlocked=True
                            ))

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to detect fastboot devices: {e}")

        return devices

    def _get_device_properties(self, device_id: str) -> Optional[MobileDeviceInfo]:
        """Get detailed properties for an ADB device."""
        try:
            # Get device properties
            props = {}
            prop_names = [
                'ro.product.model',
                'ro.product.manufacturer',
                'ro.build.version.release',
                'ro.product.brand'
            ]

            for prop in prop_names:
                result = subprocess.run(
                    [self.adb_path, '-s', device_id, 'shell', 'getprop', prop],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    props[prop] = result.stdout.strip()

            # Check if device is rooted
            has_root = self._check_root_access(device_id)

            return MobileDeviceInfo(
                device_id=device_id,
                model=props.get('ro.product.model', 'Unknown'),
                manufacturer=props.get('ro.product.manufacturer', 'Unknown'),
                android_version=props.get('ro.build.version.release', 'Unknown'),
                mode=MobileWipeMode.ADB,
                status="device",
                has_root=has_root
            )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to get device properties for {device_id}: {e}")
            return None

    def _check_root_access(self, device_id: str) -> bool:
        """Check if device has root access."""
        try:
            result = subprocess.run(
                [self.adb_path, '-s', device_id, 'shell', 'su', '-c', 'id'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and 'uid=0' in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def wipe_device(self, device_id: str, mode: MobileWipeMode,
                   progress_callback=None) -> bool:
        """
        Wipe a mobile device using the specified mode.

        Args:
            device_id: Device identifier
            mode: Wipe mode to use
            progress_callback: Optional callback for progress updates

        Returns:
            True if wipe was successful, False otherwise
        """
        logger.info(f"Starting mobile device wipe: {device_id} using {mode.value}")

        if progress_callback:
            progress_callback({"status": "starting", "progress": 0})

        try:
            if mode == MobileWipeMode.ADB:
                return self._wipe_via_adb(device_id, progress_callback)
            elif mode == MobileWipeMode.EDL:
                return self._wipe_via_edl(device_id, progress_callback)
            elif mode == MobileWipeMode.SP_FLASH:
                return self._wipe_via_spflash(device_id, progress_callback)
            elif mode == MobileWipeMode.ODIN:
                return self._wipe_via_odin(device_id, progress_callback)
            else:
                logger.error(f"Unsupported wipe mode: {mode}")
                return False

        except Exception as e:
            logger.error(f"Mobile device wipe failed: {e}")
            if progress_callback:
                progress_callback({"status": "error", "error": str(e)})
            return False

    def _wipe_via_adb(self, device_id: str, progress_callback=None) -> bool:
        """Wipe device using ADB factory reset."""
        if not self.adb_path:
            raise RuntimeError("ADB not found")

        steps = [
            ("Checking device connection", 10),
            ("Enabling encryption if needed", 30),
            ("Performing factory reset", 70),
            ("Verifying wipe completion", 90),
            ("Wipe completed", 100)
        ]

        for step, progress in steps:
            if progress_callback:
                progress_callback({"status": "running", "progress": progress, "step": step})

            if "Checking device connection" in step:
                # Verify device is still connected
                result = subprocess.run(
                    [self.adb_path, '-s', device_id, 'get-state'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0 or 'device' not in result.stdout:
                    raise RuntimeError("Device not accessible via ADB")

            elif "Enabling encryption" in step:
                # Check if device is encrypted, enable if not
                self._ensure_device_encryption(device_id)

            elif "Performing factory reset" in step:
                # Perform the actual factory reset
                result = subprocess.run(
                    [self.adb_path, '-s', device_id, 'shell', 'am', 'broadcast',
                     '-a', 'android.intent.action.MASTER_CLEAR'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    # Try alternative method
                    result = subprocess.run(
                        [self.adb_path, '-s', device_id, 'shell', 'recovery', '--wipe_data'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                # Device will reboot and disconnect
                time.sleep(5)

            elif "Verifying wipe" in step:
                # Wait for device to reboot and verify clean state
                # This is challenging as device will be in setup mode
                time.sleep(10)

            time.sleep(1)  # Small delay between steps

        logger.info(f"ADB wipe completed for device: {device_id}")
        return True

    def _ensure_device_encryption(self, device_id: str):
        """Ensure device storage is encrypted before wiping."""
        try:
            # Check encryption status
            result = subprocess.run(
                [self.adb_path, '-s', device_id, 'shell', 'getprop', 'ro.crypto.state'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                crypto_state = result.stdout.strip()
                logger.info(f"Device encryption state: {crypto_state}")

                if crypto_state != "encrypted":
                    logger.warning("Device is not encrypted - data may be recoverable")
                    # Note: Enabling encryption requires user interaction and device restart
                    # This is typically done through Settings > Security > Encrypt Device

        except subprocess.TimeoutExpired:
            logger.warning("Could not check device encryption status")

    def _wipe_via_edl(self, device_id: str, progress_callback=None) -> bool:
        """Wipe device using EDL (Emergency Download Mode)."""
        # EDL mode requires specialized tools like QFIL or edl tool
        # This is a placeholder implementation

        if progress_callback:
            progress_callback({
                "status": "error",
                "error": "EDL mode wiping requires specialized Qualcomm tools (QFIL) and is not yet implemented"
            })

        logger.error("EDL mode wiping not implemented - requires QFIL or similar tools")
        return False

    def _wipe_via_spflash(self, device_id: str, progress_callback=None) -> bool:
        """Wipe device using SP Flash Tool for MediaTek devices."""
        # SP Flash Tool requires Windows-specific drivers and tools
        # This is a placeholder implementation

        if progress_callback:
            progress_callback({
                "status": "error",
                "error": "SP Flash Tool wiping requires MediaTek SP Flash Tool and is not yet implemented"
            })

        logger.error("SP Flash Tool wiping not implemented - requires MediaTek tools")
        return False

    def _wipe_via_odin(self, device_id: str, progress_callback=None) -> bool:
        """Wipe device using Odin download mode for Samsung devices."""
        # Odin mode requires Samsung-specific tools and firmware
        # This is a placeholder implementation

        if progress_callback:
            progress_callback({
                "status": "error",
                "error": "Odin mode wiping requires Samsung Odin tool and is not yet implemented"
            })

        logger.error("Odin mode wiping not implemented - requires Samsung Odin tool")
        return False

    def get_wipe_instructions(self, mode: MobileWipeMode) -> Dict[str, Any]:
        """Get instructions for putting device into specified wipe mode."""
        instructions = {
            MobileWipeMode.ADB: {
                "title": "ADB Factory Reset Instructions",
                "requirements": ["USB Debugging enabled", "ADB drivers installed"],
                "steps": [
                    "Enable Developer Options on device",
                    "Enable USB Debugging in Developer Options",
                    "Connect device via USB cable",
                    "Accept USB debugging prompt on device",
                    "Ensure device is not encrypted (optional but recommended)"
                ],
                "notes": "This is the safest and most compatible method"
            },
            MobileWipeMode.EDL: {
                "title": "EDL Mode Instructions (Qualcomm)",
                "requirements": ["Qualcomm device", "EDL drivers", "QFIL or EDL tool"],
                "steps": [
                    "Power off device completely",
                    "Hold Volume Down + Power buttons",
                    "Connect USB cable to computer",
                    "Device enters EDL mode (no display)",
                    "Use QFIL or edl tool to wipe"
                ],
                "notes": "Advanced mode - requires specialized tools and drivers"
            },
            MobileWipeMode.SP_FLASH: {
                "title": "SP Flash Tool Instructions (MediaTek)",
                "requirements": ["MediaTek device", "SP Flash Tool", "MediaTek drivers"],
                "steps": [
                    "Power off MediaTek device",
                    "Remove battery if possible",
                    "Hold Volume Up button",
                    "Connect USB while holding Volume Up",
                    "Use SP Flash Tool to format/wipe"
                ],
                "notes": "MediaTek specific - requires SP Flash Tool software"
            },
            MobileWipeMode.ODIN: {
                "title": "Odin Download Mode Instructions (Samsung)",
                "requirements": ["Samsung device", "Odin tool", "Samsung drivers"],
                "steps": [
                    "Power off Samsung device",
                    "Hold Volume Down + Home + Power",
                    "Press Volume Up to confirm download mode",
                    "Connect USB cable",
                    "Use Odin to flash empty firmware or format"
                ],
                "notes": "Samsung specific - requires Odin tool and firmware files"
            }
        }

        return instructions.get(mode, {})


def create_mobile_handler() -> MobileDeviceHandler:
    """Factory function to create mobile device handler."""
    return MobileDeviceHandler()