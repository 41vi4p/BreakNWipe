"""
Session Manager for BreakNWipe Web Interface

Manages concurrent wipe sessions with threading support and progress tracking.
"""

import threading
import uuid
import time
import asyncio
import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ..device import DeviceDetector, DeviceHandler
from ..device.storage import DeviceInterface
from ..wipe_engine import WipeEngine, create_algorithm
from ..certificate import CertificateGenerator
from ..logging import WipeLoggingService
from .models import (
    WipeSession, WipeProgress, WipeRequest, DeviceInfo,
    WipeSessionStatus, DeviceType, WipeAlgorithm
)

logger = logging.getLogger(__name__)


class WipeSessionManager:
    """Manages multiple concurrent wipe sessions."""

    def __init__(self, max_concurrent_wipes: int = 3):
        """Initialize the session manager."""
        self.sessions: Dict[str, WipeSession] = {}
        self.progress_callbacks: Dict[str, List[callable]] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_wipes)
        self.device_detector = DeviceDetector()
        self.cert_generator = CertificateGenerator()
        self.logger = WipeLoggingService()
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

        # Log wipe operation start
        try:
            device_dict = {
                'path': device_info.path,
                'model': device_info.model,
                'serial': device_info.serial,
                'capacity': device_info.capacity,
                'capacity_human': device_info.capacity_human,
                'interface': device_info.interface,
                'device_type': device_info.device_type.value
            }
            wipe_dict = {
                'algorithm': wipe_request.algorithm.value,
                'total_passes': self._get_total_passes(wipe_request.algorithm),
                'verify': wipe_request.verify,
                'generate_certificate': wipe_request.generate_certificate
            }
            self.logger.log_wipe_started(session_id, device_dict, wipe_dict)
        except Exception as e:
            print(f"Failed to log wipe start: {e}")

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

                # Log cancellation
                try:
                    self.logger.log_wipe_cancelled(session_id, "User cancelled operation")
                except Exception as e:
                    print(f"Failed to log wipe cancellation: {e}")

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
            WipeAlgorithm.NIST_CLEAR: 1,
            WipeAlgorithm.NIST_PURGE: 3,
            WipeAlgorithm.DOD_3PASS: 3,
            WipeAlgorithm.DOD_7PASS: 7,
            WipeAlgorithm.GUTMANN: 35,
            WipeAlgorithm.RANDOM: 3,
            WipeAlgorithm.ZEROS: 1,
            WipeAlgorithm.CUSTOM: 3,
            WipeAlgorithm.REA_BASIC: 5,
            WipeAlgorithm.REA_MULTICHAIN: 8,
            WipeAlgorithm.REA_EXTREME: 32,
            WipeAlgorithm.REA_CUSTOM: 6
        }
        return algorithm_passes.get(algorithm, 3)

    def _execute_wipe(self, session_id: str):
        """Execute the wipe operation in a background thread."""
        session = self.sessions[session_id]

        try:
            # Update status to running
            session.progress.status = WipeSessionStatus.RUNNING
            session.progress.started_at = datetime.now()
            session.progress.last_updated = datetime.now()
            self._notify_progress_callbacks(session_id)

            # Setup progress callback
            def progress_callback(progress):
                # Convert engine progress to session progress
                session.progress.current_pass = progress.current_pass
                session.progress.total_passes = progress.total_passes
                session.progress.progress_percent = progress.overall_progress * 100
                session.progress.speed_mbps = progress.current_speed_mbps
                session.progress.data_processed = progress.bytes_written
                session.progress.last_updated = datetime.now()

                # Estimate remaining time
                if progress.eta_seconds > 0:
                    session.progress.estimated_remaining = progress.eta_seconds

                # Log progress updates (only every 10%)
                try:
                    progress_data = {
                        'status': session.progress.status.value,
                        'progress_percent': session.progress.progress_percent,
                        'data_processed': session.progress.data_processed,
                        'speed_mbps': session.progress.speed_mbps
                    }
                    self.logger.log_wipe_progress(session_id, progress_data)
                except Exception as e:
                    pass  # Don't let logging errors interrupt wipe

                self._notify_progress_callbacks(session_id)
                return session.progress.status != WipeSessionStatus.CANCELLED

            # Create wipe engine and algorithm
            engine = WipeEngine(progress_callback=progress_callback)

            # Map algorithm names
            algorithm_mapping = {
                WipeAlgorithm.NIST_CLEAR: 'nist-clear',
                WipeAlgorithm.NIST_PURGE: 'nist-purge',
                WipeAlgorithm.DOD_3PASS: 'dod-3pass',
                WipeAlgorithm.DOD_7PASS: 'dod-7pass',
                WipeAlgorithm.GUTMANN: 'gutmann',
                WipeAlgorithm.RANDOM: 'random',
                WipeAlgorithm.ZEROS: 'zeros',
                WipeAlgorithm.CUSTOM: 'custom',
                WipeAlgorithm.REA_BASIC: 'rea-basic',
                WipeAlgorithm.REA_MULTICHAIN: 'rea-multichain',
                WipeAlgorithm.REA_EXTREME: 'rea-extreme',
                WipeAlgorithm.REA_CUSTOM: 'rea-custom'
            }

            algorithm_name = algorithm_mapping.get(session.wipe_request.algorithm, 'nist-clear')
            algorithm = create_algorithm(algorithm_name)

            # Create device handler (for hardware operations if needed)
            device_handler = DeviceHandler()

            # Execute wipe
            result = engine.wipe_device(
                device_path=session.device_info.path,
                algorithm=algorithm,
                verify=session.wipe_request.verify
            )

            if session.progress.status == WipeSessionStatus.CANCELLED:
                return

            # Generate report ID once and store it in the session
            if not hasattr(session, 'report_id') or not session.report_id:
                session.report_id = f"BNW-{session_id[:8]}-{int(time.time())}"

            # Generate certificate if requested
            if session.wipe_request.generate_certificate and result.success:
                try:
                    # Import here to avoid circular imports
                    from ..certificate.report import WipeReport, DeviceInfo as ReportDeviceInfo

                    # Create WipeReport from result
                    report_device_info = ReportDeviceInfo(
                        path=session.device_info.path,
                        model=session.device_info.model,
                        serial=session.device_info.serial,
                        capacity_bytes=session.device_info.capacity,
                        capacity_human=session.device_info.capacity_human,
                        device_type=session.device_info.device_type.value,
                        interface=session.device_info.interface
                    )

                    wipe_report = WipeReport(
                        report_id=session.report_id,  # Use the consistent report ID
                        device_info=report_device_info,
                        algorithm_used=result.algorithm_used,
                        wipe_method="software",
                        start_time=result.start_time,
                        end_time=result.end_time,
                        total_passes=result.total_passes,
                        success=result.success,
                        total_bytes_written=result.total_bytes_written,
                        average_speed_mbps=result.average_speed_mbps,
                        organization="BreakNWipe by CodeBreakers",
                        operator="System User"
                    )

                    # Add session ID to the report for QR code generation
                    wipe_report.session_id = session_id

                    # Check internet connectivity for blockchain upload
                    from ..utils import check_internet_connectivity, check_blockchain_service_connectivity

                    # Read blockchain config
                    blockchain_config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'blockchain_config.json')
                    auto_blockchain = True  # Default to auto-upload
                    blockchain_rpc_url = None

                    try:
                        if os.path.exists(blockchain_config_path):
                            with open(blockchain_config_path, 'r') as f:
                                config = json.load(f)
                                auto_blockchain = config.get('breaknwipe', {}).get('auto_blockchain_store', True)
                                blockchain_rpc_url = config.get('network', {}).get('rpc_url')
                    except Exception as e:
                        logger.debug(f"Could not read blockchain config: {e}")

                    # Check connectivity and attempt blockchain upload
                    store_on_blockchain = False
                    if auto_blockchain:
                        if check_internet_connectivity():
                            logger.info("Internet connectivity detected, attempting blockchain upload")
                            if blockchain_rpc_url and check_blockchain_service_connectivity(blockchain_rpc_url):
                                store_on_blockchain = True
                                logger.info("Blockchain service is reachable, will upload to blockchain")
                            else:
                                logger.warning("Blockchain service is not reachable, skipping blockchain upload")
                        else:
                            logger.warning("No internet connectivity, skipping blockchain upload")

                    # Generate certificate with blockchain upload if available
                    cert_files = self.cert_generator.generate_certificate(
                        wipe_report,
                        include_qr=True,
                        store_on_blockchain=store_on_blockchain
                    )
                    session.certificate_path = cert_files.get('pdf', '')

                    # Store the QR data that was generated for the certificate
                    blockchain_result = cert_files.get('blockchain_result')
                    qr_data = self.cert_generator._generate_qr_data(wipe_report, blockchain_result)
                    session.qr_data = qr_data

                    # Log blockchain result if available
                    if blockchain_result:
                        if blockchain_result.get('success'):
                            logger.info(f"Certificate successfully uploaded to blockchain: {blockchain_result.get('transaction_hash', 'Already exists')}")
                        else:
                            logger.error(f"Failed to upload to blockchain: {blockchain_result.get('error', 'Unknown error')}")

                    # Store report in database
                    try:
                        # Prepare report data for storage
                        report_data = {
                            'device_path': session.device_info.path,
                            'device_model': session.device_info.model,
                            'device_serial': session.device_info.serial,
                            'algorithm_used': result.algorithm_used,
                            'wipe_method': 'software',
                            'start_time': result.start_time,
                            'end_time': result.end_time,
                            'total_passes': result.total_passes,
                            'success': result.success,
                            'total_bytes_written': result.total_bytes_written,
                            'average_speed_mbps': result.average_speed_mbps,
                            'organization': 'BreakNWipe by CodeBreakers',
                            'operator': 'System User'
                        }

                        # Store the report with certificate files
                        self.logger.store_wipe_report(
                            session_id=session_id,
                            report_data=report_data,
                            certificate_files=cert_files
                        )
                    except Exception as e:
                        print(f"Failed to store report in database: {e}")

                except Exception as e:
                    print(f"Certificate generation failed: {e}")

            # Log wipe completion
            try:
                result_data = {
                    'success': result.success,
                    'total_bytes_written': result.total_bytes_written,
                    'average_speed_mbps': result.average_speed_mbps,
                    'error_message': getattr(result, 'error_message', None)
                }
                self.logger.log_wipe_completed(
                    session_id,
                    result_data,
                    getattr(session, 'certificate_path', None),
                    session.report_id
                )
            except Exception as e:
                print(f"Failed to log wipe completion: {e}")

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

            # Log failure
            try:
                result_data = {
                    'success': False,
                    'error_message': str(e)
                }
                self.logger.log_wipe_completed(session_id, result_data)
            except Exception as log_error:
                print(f"Failed to log wipe failure: {log_error}")

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