"""
Session Manager for BreakNWipe Web Interface

Manages concurrent wipe sessions with threading support and progress tracking.
"""

import threading
import uuid
import time
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ..device import DeviceDetector, DeviceHandler
from ..device.storage import DeviceInterface
from ..wipe_engine import WipeEngine, create_algorithm
from ..certificate import CertificateGenerator
from .models import (
    WipeSession, WipeProgress, WipeRequest, DeviceInfo,
    WipeSessionStatus, DeviceType, WipeAlgorithm
)


class WipeSessionManager:
    """Manages multiple concurrent wipe sessions."""

    def __init__(self, max_concurrent_wipes: int = 3):
        """Initialize the session manager."""
        self.sessions: Dict[str, WipeSession] = {}
        self.progress_callbacks: Dict[str, List[callable]] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_wipes)
        self.device_detector = DeviceDetector()
        self.cert_generator = CertificateGenerator()
        self._lock = threading.RLock()

    def get_available_devices(self) -> List[DeviceInfo]:
        """Get list of available storage devices."""
        try:
            devices = self.device_detector.list_devices()
            device_list = []

            for device in devices:
                # Map device type based on characteristics
                device_type = DeviceType.UNKNOWN
                if hasattr(device, 'device_type'):
                    type_mapping = {
                        'hdd': DeviceType.SERVER,
                        'ssd_sata': DeviceType.LAPTOP,
                        'ssd_nvme': DeviceType.LAPTOP,
                        'usb_flash': DeviceType.EXTERNAL,
                        'sd_card': DeviceType.EXTERNAL,
                        'emmc': DeviceType.MOBILE,
                        'unknown': DeviceType.UNKNOWN
                    }
                    device_type_value = device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type)
                    device_type = type_mapping.get(device_type_value, DeviceType.UNKNOWN)

                device_info = DeviceInfo(
                    path=device.path,
                    model=device.model,
                    serial=device.serial,
                    capacity=device.capacity_bytes,
                    capacity_human=device.capacity_human,
                    device_type=device_type,
                    interface=getattr(device, 'interface', DeviceInterface.UNKNOWN).value if hasattr(getattr(device, 'interface', DeviceInterface.UNKNOWN), 'value') else str(getattr(device, 'interface', 'Unknown')),
                    is_mounted=device.is_mounted,
                    secure_erase_support=getattr(device, 'secure_erase_support', False)
                )
                device_list.append(device_info)

            return device_list
        except Exception as e:
            print(f"Error getting devices: {e}")
            return []

    def start_wipe_session(self, wipe_request: WipeRequest) -> str:
        """Start a new wipe session."""
        session_id = str(uuid.uuid4())

        # Get device info
        devices = self.get_available_devices()
        device_info = None
        for device in devices:
            if device.path == wipe_request.device_path:
                device_info = device
                break

        if not device_info:
            raise ValueError(f"Device {wipe_request.device_path} not found")

        # Create initial progress
        progress = WipeProgress(
            session_id=session_id,
            status=WipeSessionStatus.PENDING,
            progress_percent=0.0,
            current_pass=0,
            total_passes=self._get_total_passes(wipe_request.algorithm),
            speed_mbps=0.0,
            data_processed=0,
            started_at=datetime.now(),
            last_updated=datetime.now()
        )

        # Create session
        session = WipeSession(
            session_id=session_id,
            device_info=device_info,
            wipe_request=wipe_request,
            progress=progress
        )

        with self._lock:
            self.sessions[session_id] = session
            self.progress_callbacks[session_id] = []

        # Submit wipe task to thread pool
        self.executor.submit(self._execute_wipe, session_id)

        return session_id

    def get_session(self, session_id: str) -> Optional[WipeSession]:
        """Get session information."""
        with self._lock:
            return self.sessions.get(session_id)

    def get_all_sessions(self) -> List[WipeSession]:
        """Get all active sessions."""
        with self._lock:
            return list(self.sessions.values())

    def cancel_session(self, session_id: str) -> bool:
        """Cancel a running wipe session."""
        with self._lock:
            session = self.sessions.get(session_id)
            if session and session.progress.status == WipeSessionStatus.RUNNING:
                session.progress.status = WipeSessionStatus.CANCELLED
                session.progress.last_updated = datetime.now()
                return True
            return False

    def add_progress_callback(self, session_id: str, callback: callable):
        """Add a callback for progress updates."""
        with self._lock:
            if session_id in self.progress_callbacks:
                self.progress_callbacks[session_id].append(callback)

    def remove_progress_callback(self, session_id: str, callback: callable):
        """Remove a progress callback."""
        with self._lock:
            if session_id in self.progress_callbacks:
                try:
                    self.progress_callbacks[session_id].remove(callback)
                except ValueError:
                    pass

    def _get_total_passes(self, algorithm: WipeAlgorithm) -> int:
        """Get total number of passes for an algorithm."""
        algorithm_passes = {
            WipeAlgorithm.ZERO_FILL: 1,
            WipeAlgorithm.RANDOM_FILL: 1,
            WipeAlgorithm.DOD: 3,
            WipeAlgorithm.GUTMANN: 35,
            WipeAlgorithm.NIST_CLEAR: 1,
            WipeAlgorithm.NIST_PURGE: 3
        }
        return algorithm_passes.get(algorithm, 3)

    def _execute_wipe(self, session_id: str):
        """Execute the wipe operation in a background thread."""
        session = self.sessions[session_id]

        try:
            # Update status to running
            session.progress.status = WipeSessionStatus.RUNNING
            session.progress.last_updated = datetime.now()
            self._notify_progress_callbacks(session_id)

            # Create wipe engine and algorithm
            engine = WipeEngine()

            # Map algorithm names
            algorithm_mapping = {
                WipeAlgorithm.ZERO_FILL: 'zeros',
                WipeAlgorithm.RANDOM_FILL: 'random',
                WipeAlgorithm.DOD: 'dod-3pass',
                WipeAlgorithm.GUTMANN: 'gutmann',
                WipeAlgorithm.NIST_CLEAR: 'nist-clear',
                WipeAlgorithm.NIST_PURGE: 'nist-purge'
            }

            algorithm_name = algorithm_mapping.get(session.wipe_request.algorithm, 'nist-clear')
            algorithm = create_algorithm(algorithm_name)

            # Create device handler
            device_handler = DeviceHandler(session.device_info.path)

            # Setup progress callback
            def progress_callback(pass_num, total_passes, progress_percent, speed_mbps, data_processed):
                if session.progress.status == WipeSessionStatus.CANCELLED:
                    return False  # Signal to stop

                session.progress.current_pass = pass_num
                session.progress.total_passes = total_passes
                session.progress.progress_percent = progress_percent
                session.progress.speed_mbps = speed_mbps
                session.progress.data_processed = data_processed
                session.progress.last_updated = datetime.now()

                # Estimate remaining time
                if speed_mbps > 0 and progress_percent > 0:
                    remaining_data = session.device_info.capacity * (100 - progress_percent) / 100
                    remaining_time = remaining_data / (speed_mbps * 1024 * 1024)
                    session.progress.estimated_remaining = int(remaining_time)

                self._notify_progress_callbacks(session_id)
                return True  # Continue

            # Execute wipe
            result = engine.wipe_device(
                device_handler=device_handler,
                algorithm=algorithm,
                verify=session.wipe_request.verify,
                progress_callback=progress_callback
            )

            if session.progress.status == WipeSessionStatus.CANCELLED:
                return

            # Generate certificate if requested
            if session.wipe_request.generate_certificate and result.success:
                try:
                    cert_path = self.cert_generator.generate_certificate(result)
                    session.certificate_path = cert_path
                except Exception as e:
                    print(f"Certificate generation failed: {e}")

            # Update final status
            if result.success:
                session.progress.status = WipeSessionStatus.COMPLETED
                session.progress.progress_percent = 100.0
            else:
                session.progress.status = WipeSessionStatus.FAILED
                session.error_message = str(result.error) if hasattr(result, 'error') else "Wipe operation failed"

        except Exception as e:
            session.progress.status = WipeSessionStatus.FAILED
            session.error_message = str(e)
            print(f"Wipe operation failed: {e}")

        finally:
            session.progress.last_updated = datetime.now()
            self._notify_progress_callbacks(session_id)

    def _notify_progress_callbacks(self, session_id: str):
        """Notify all registered progress callbacks."""
        with self._lock:
            session = self.sessions.get(session_id)
            if session and session_id in self.progress_callbacks:
                for callback in self.progress_callbacks[session_id]:
                    try:
                        callback(session.progress)
                    except Exception as e:
                        print(f"Error in progress callback: {e}")

    def cleanup_completed_sessions(self, max_age_hours: int = 24):
        """Clean up old completed sessions."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        with self._lock:
            sessions_to_remove = []
            for session_id, session in self.sessions.items():
                if (session.progress.status in [WipeSessionStatus.COMPLETED, WipeSessionStatus.FAILED, WipeSessionStatus.CANCELLED] and
                    session.progress.last_updated.timestamp() < cutoff_time):
                    sessions_to_remove.append(session_id)

            for session_id in sessions_to_remove:
                del self.sessions[session_id]
                if session_id in self.progress_callbacks:
                    del self.progress_callbacks[session_id]