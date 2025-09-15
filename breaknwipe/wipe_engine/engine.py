"""
Wipe Engine Core

Main engine for performing secure data wiping operations.
Handles device access, progress tracking, and verification.
"""

import os
import time
import hashlib
import logging
from typing import Optional, Callable, Generator, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from .algorithms import WipeAlgorithm, WipePass
from .verification import WipeVerifier

logger = logging.getLogger(__name__)


@dataclass
class WipeProgress:
    """Progress information for wipe operation."""
    current_pass: int
    total_passes: int
    current_pass_progress: float  # 0.0 to 1.0
    overall_progress: float       # 0.0 to 1.0
    bytes_written: int
    total_bytes: int
    current_speed_mbps: float
    average_speed_mbps: float
    eta_seconds: int
    pass_description: str
    status: str


@dataclass
class WipeResult:
    """Result of wipe operation."""
    success: bool
    device_path: str
    algorithm_used: str
    total_passes: int
    start_time: float
    end_time: float
    total_bytes_written: int
    average_speed_mbps: float
    verification_passed: bool
    error_message: Optional[str] = None
    pass_results: list = None


class WipeEngine:
    """Core engine for secure data wiping operations."""

    def __init__(self, progress_callback: Optional[Callable[[WipeProgress], None]] = None):
        """
        Initialize wipe engine.

        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback
        self.verifier = WipeVerifier()
        self._cancel_requested = False

    def wipe_device(self, device_path: str, algorithm: WipeAlgorithm,
                   verify: bool = True, dry_run: bool = False) -> WipeResult:
        """
        Perform secure wipe of specified device.

        Args:
            device_path: Path to device to wipe (e.g., /dev/sda)
            algorithm: Wipe algorithm to use
            verify: Whether to verify wipe completion
            dry_run: If True, simulate wipe without actually writing

        Returns:
            WipeResult with operation details
        """
        logger.info(f"Starting wipe operation: {device_path} with {algorithm.get_description()}")

        start_time = time.time()
        device_size = self._get_device_size(device_path)
        total_passes = algorithm.get_total_passes()

        if dry_run:
            logger.info("DRY RUN MODE - No actual data will be written")

        try:
            # Validate device access
            self._validate_device(device_path, dry_run)

            # Perform wipe passes
            pass_results = []
            total_bytes_written = 0

            for pass_info in algorithm.get_passes():
                if self._cancel_requested:
                    raise InterruptedError("Wipe operation cancelled by user")

                logger.info(f"Starting {pass_info.description}")

                pass_result = self._execute_pass(
                    device_path, device_size, pass_info, algorithm.get_total_passes(),
                    dry_run
                )

                pass_results.append(pass_result)
                total_bytes_written += pass_result['bytes_written']

                if not pass_result['success']:
                    raise RuntimeError(f"Pass {pass_info.pass_number} failed: {pass_result['error']}")

            # Verification phase
            verification_passed = True
            if verify and not dry_run:
                logger.info("Starting verification phase")
                verification_passed = self._verify_wipe(device_path, device_size)

            end_time = time.time()
            duration = end_time - start_time
            average_speed = (total_bytes_written / (1024 * 1024)) / duration if duration > 0 else 0

            return WipeResult(
                success=True,
                device_path=device_path,
                algorithm_used=algorithm.get_description(),
                total_passes=total_passes,
                start_time=start_time,
                end_time=end_time,
                total_bytes_written=total_bytes_written,
                average_speed_mbps=average_speed,
                verification_passed=verification_passed,
                pass_results=pass_results
            )

        except Exception as e:
            logger.error(f"Wipe operation failed: {e}")
            return WipeResult(
                success=False,
                device_path=device_path,
                algorithm_used=algorithm.get_description(),
                total_passes=total_passes,
                start_time=start_time,
                end_time=time.time(),
                total_bytes_written=total_bytes_written,
                average_speed_mbps=0,
                verification_passed=False,
                error_message=str(e)
            )

    def _validate_device(self, device_path: str, dry_run: bool = False):
        """Validate device accessibility and safety."""
        if not dry_run and not os.path.exists(device_path):
            raise FileNotFoundError(f"Device not found: {device_path}")

        if not dry_run and not os.access(device_path, os.R_OK | os.W_OK):
            raise PermissionError(f"Insufficient permissions for device: {device_path}")

        # Check if device is mounted
        if not dry_run:
            mounted_check = os.popen(f"mount | grep '{device_path}'").read()
            if mounted_check.strip():
                raise RuntimeError(f"Device is mounted: {device_path}. Unmount before wiping.")

    def _get_device_size(self, device_path: str) -> int:
        """Get device size in bytes."""
        try:
            with open(device_path, 'rb') as device:
                device.seek(0, 2)  # Seek to end
                size = device.tell()
                device.seek(0)     # Reset to beginning
                return size
        except Exception as e:
            logger.warning(f"Could not determine device size: {e}")
            # Fallback: try using blockdev command
            try:
                result = os.popen(f"blockdev --getsize64 '{device_path}' 2>/dev/null").read()
                return int(result.strip()) if result.strip() else 0
            except:
                return 0

    def _execute_pass(self, device_path: str, device_size: int, pass_info: WipePass,
                     total_passes: int, dry_run: bool = False) -> Dict[str, Any]:
        """Execute a single wipe pass."""

        start_time = time.time()
        bytes_written = 0
        block_size = len(pass_info.pattern)

        if dry_run:
            # Simulate the operation
            time.sleep(0.1)  # Simulate some work
            return {
                'pass_number': pass_info.pass_number,
                'success': True,
                'bytes_written': device_size,
                'duration': 0.1,
                'error': None
            }

        try:
            with open(device_path, 'r+b', buffering=0) as device:
                position = 0

                while position < device_size and not self._cancel_requested:
                    # Calculate remaining bytes and adjust block size if needed
                    remaining = device_size - position
                    current_block_size = min(block_size, remaining)

                    # Get pattern data for this block
                    if current_block_size == block_size:
                        write_data = pass_info.pattern
                    else:
                        write_data = pass_info.pattern[:current_block_size]

                    # Write the data
                    device.seek(position)
                    written = device.write(write_data)
                    device.flush()
                    os.fsync(device.fileno())

                    bytes_written += written
                    position += written

                    # Update progress
                    if self.progress_callback:
                        pass_progress = position / device_size
                        overall_progress = ((pass_info.pass_number - 1) + pass_progress) / total_passes

                        current_time = time.time()
                        duration = current_time - start_time
                        speed = (bytes_written / (1024 * 1024)) / duration if duration > 0 else 0

                        progress = WipeProgress(
                            current_pass=pass_info.pass_number,
                            total_passes=total_passes,
                            current_pass_progress=pass_progress,
                            overall_progress=overall_progress,
                            bytes_written=bytes_written,
                            total_bytes=device_size,
                            current_speed_mbps=speed,
                            average_speed_mbps=speed,
                            eta_seconds=int((device_size - position) / (speed * 1024 * 1024)) if speed > 0 else 0,
                            pass_description=pass_info.description,
                            status="Writing"
                        )

                        self.progress_callback(progress)

            duration = time.time() - start_time

            return {
                'pass_number': pass_info.pass_number,
                'success': True,
                'bytes_written': bytes_written,
                'duration': duration,
                'error': None
            }

        except Exception as e:
            return {
                'pass_number': pass_info.pass_number,
                'success': False,
                'bytes_written': bytes_written,
                'duration': time.time() - start_time,
                'error': str(e)
            }

    def _verify_wipe(self, device_path: str, device_size: int) -> bool:
        """Verify that wipe operation was successful."""
        try:
            return self.verifier.verify_wipe(device_path, device_size)
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def cancel_operation(self):
        """Cancel the current wipe operation."""
        self._cancel_requested = True
        logger.info("Wipe operation cancellation requested")

    def reset_cancel_flag(self):
        """Reset the cancel flag for new operations."""
        self._cancel_requested = False


def format_bytes(bytes_count: int) -> str:
    """Format bytes into human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.1f} PB"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"