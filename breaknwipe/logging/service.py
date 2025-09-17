"""
Wipe Logging Service

High-level service for logging wipe operations and managing audit trails.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from .database import LoggingDatabase, WipeLogEntry

logger = logging.getLogger(__name__)


class WipeLoggingService:
    """Service for logging wipe operations and audit events."""

    def __init__(self, db_path: str = None):
        """
        Initialize the logging service.

        Args:
            db_path: Path to SQLite database file
        """
        self.db = LoggingDatabase(db_path)

    def log_wipe_started(self, session_id: str, device_info: Dict[str, Any],
                        wipe_request: Dict[str, Any], user_agent: str = None,
                        ip_address: str = None) -> int:
        """
        Log the start of a wipe operation.

        Args:
            session_id: Unique session identifier
            device_info: Device information dictionary
            wipe_request: Wipe request parameters
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Database record ID
        """
        log_entry = WipeLogEntry(
            session_id=session_id,
            device_path=device_info.get('path', ''),
            device_model=device_info.get('model', ''),
            device_serial=device_info.get('serial', ''),
            device_capacity_bytes=device_info.get('capacity', 0),
            device_capacity_human=device_info.get('capacity_human', ''),
            device_interface=device_info.get('interface', ''),
            device_type=device_info.get('device_type', ''),
            algorithm_used=wipe_request.get('algorithm', ''),
            total_passes=wipe_request.get('total_passes', 0),
            verification_enabled=wipe_request.get('verify', False),
            certificate_generated=wipe_request.get('generate_certificate', False),
            operation_status='pending',
            started_at=datetime.now(),
            created_at=datetime.now()
        )

        record_id = self.db.add_wipe_log(log_entry)

        # Add audit event
        self.db.add_audit_event(
            session_id=session_id,
            event_type='wipe_started',
            description=f'Wipe operation started for {device_info.get("model", "unknown device")}',
            event_data={
                'device_path': device_info.get('path'),
                'algorithm': wipe_request.get('algorithm'),
                'verification': wipe_request.get('verify')
            },
            user_agent=user_agent,
            ip_address=ip_address
        )

        logger.info(f"Logged wipe start: session_id={session_id}, device={device_info.get('path')}")
        return record_id

    def log_wipe_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """
        Log wipe operation progress.

        Args:
            session_id: Session identifier
            progress_data: Progress information
        """
        updates = {
            'operation_status': progress_data.get('status', 'running'),
            'progress_percent': progress_data.get('progress_percent', 0.0),
            'data_processed_bytes': progress_data.get('data_processed', 0),
            'average_speed_mbps': progress_data.get('speed_mbps', 0.0)
        }

        # Only update significant progress changes to avoid spam
        if progress_data.get('progress_percent', 0) % 10 == 0:
            self.db.update_wipe_log(session_id, updates)

    def log_wipe_completed(self, session_id: str, result_data: Dict[str, Any],
                          certificate_path: str = None, report_id: str = None):
        """
        Log the completion of a wipe operation.

        Args:
            session_id: Session identifier
            result_data: Operation result data
            certificate_path: Path to generated certificate
            report_id: Generated report ID
        """
        completed_at = datetime.now()

        # Get the original log to calculate duration
        original_log = self.db.get_wipe_log(session_id)
        duration_seconds = 0
        if original_log and original_log.get('started_at'):
            started_at = datetime.fromisoformat(original_log['started_at'])
            duration_seconds = int((completed_at - started_at).total_seconds())

        updates = {
            'operation_status': 'completed' if result_data.get('success') else 'failed',
            'progress_percent': 100.0 if result_data.get('success') else result_data.get('progress_percent', 0),
            'data_processed_bytes': result_data.get('total_bytes_written', 0),
            'average_speed_mbps': result_data.get('average_speed_mbps', 0.0),
            'completed_at': completed_at,
            'duration_seconds': duration_seconds,
            'error_message': result_data.get('error_message'),
            'certificate_path': certificate_path,
            'report_id': report_id
        }

        self.db.update_wipe_log(session_id, updates)

        # Add audit event
        status = 'completed' if result_data.get('success') else 'failed'
        self.db.add_audit_event(
            session_id=session_id,
            event_type=f'wipe_{status}',
            description=f'Wipe operation {status}',
            event_data={
                'duration_seconds': duration_seconds,
                'data_processed': result_data.get('total_bytes_written', 0),
                'success': result_data.get('success', False)
            }
        )

        logger.info(f"Logged wipe completion: session_id={session_id}, status={status}")

    def log_wipe_cancelled(self, session_id: str, reason: str = None,
                          user_agent: str = None, ip_address: str = None):
        """
        Log the cancellation of a wipe operation.

        Args:
            session_id: Session identifier
            reason: Reason for cancellation
            user_agent: User agent string
            ip_address: Client IP address
        """
        completed_at = datetime.now()

        # Get the original log to calculate duration
        original_log = self.db.get_wipe_log(session_id)
        duration_seconds = 0
        if original_log and original_log.get('started_at'):
            started_at = datetime.fromisoformat(original_log['started_at'])
            duration_seconds = int((completed_at - started_at).total_seconds())

        updates = {
            'operation_status': 'cancelled',
            'completed_at': completed_at,
            'duration_seconds': duration_seconds,
            'error_message': f'Operation cancelled: {reason}' if reason else 'Operation cancelled by user'
        }

        self.db.update_wipe_log(session_id, updates)

        # Add audit event
        self.db.add_audit_event(
            session_id=session_id,
            event_type='wipe_cancelled',
            description='Wipe operation cancelled by user',
            event_data={
                'reason': reason,
                'duration_seconds': duration_seconds
            },
            user_agent=user_agent,
            ip_address=ip_address
        )

        logger.info(f"Logged wipe cancellation: session_id={session_id}")

    def get_logs(self, device_path: str = None, status: str = None,
                limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get wipe logs with optional filtering.

        Args:
            device_path: Filter by device path
            status: Filter by operation status
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of log dictionaries
        """
        return self.db.get_wipe_logs(device_path, status, limit, offset)

    def get_device_logs(self, device_path: str) -> List[Dict[str, Any]]:
        """
        Get all logs for a specific device.

        Args:
            device_path: Device path to filter by

        Returns:
            List of log dictionaries for the device
        """
        return self.db.get_wipe_logs(device_path=device_path, limit=1000)

    def get_device_history(self, device_path: str = None) -> List[Dict[str, Any]]:
        """
        Get device history records.

        Args:
            device_path: Specific device path, or None for all devices

        Returns:
            List of device history dictionaries
        """
        return self.db.get_device_history(device_path)

    def get_log_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific log by session ID.

        Args:
            session_id: Session ID to search for

        Returns:
            Log dictionary or None if not found
        """
        return self.db.get_wipe_log(session_id)

    def get_audit_trail(self, session_id: str = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit trail events.

        Args:
            session_id: Filter by session ID
            limit: Maximum number of records

        Returns:
            List of audit event dictionaries
        """
        return self.db.get_audit_trail(session_id, limit)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive logging statistics.

        Returns:
            Dictionary with various statistics
        """
        stats = self.db.get_statistics()

        # Add additional computed statistics
        logs = self.db.get_wipe_logs(limit=1000)

        # Calculate success rate
        completed_logs = [log for log in logs if log['operation_status'] == 'completed']
        failed_logs = [log for log in logs if log['operation_status'] == 'failed']
        total_completed_or_failed = len(completed_logs) + len(failed_logs)

        if total_completed_or_failed > 0:
            stats['success_rate'] = (len(completed_logs) / total_completed_or_failed) * 100
        else:
            stats['success_rate'] = 0

        # Calculate average operation time
        completed_with_duration = [log for log in completed_logs if log['duration_seconds']]
        if completed_with_duration:
            avg_duration = sum(log['duration_seconds'] for log in completed_with_duration) / len(completed_with_duration)
            stats['average_duration_seconds'] = int(avg_duration)
        else:
            stats['average_duration_seconds'] = 0

        # Calculate total data processed
        stats['total_data_processed_bytes'] = sum(
            log['data_processed_bytes'] or 0 for log in logs
        )

        return stats

    def search_logs(self, search_term: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search logs by device model, serial, or path.

        Args:
            search_term: Term to search for
            limit: Maximum number of results

        Returns:
            List of matching log dictionaries
        """
        all_logs = self.db.get_wipe_logs(limit=limit * 2)  # Get more to search through

        # Simple text search
        search_term = search_term.lower()
        matching_logs = []

        for log in all_logs:
            if (search_term in (log.get('device_model') or '').lower() or
                search_term in (log.get('device_serial') or '').lower() or
                search_term in (log.get('device_path') or '').lower() or
                search_term in (log.get('algorithm_used') or '').lower()):
                matching_logs.append(log)

                if len(matching_logs) >= limit:
                    break

        return matching_logs

    def store_wipe_report(self, session_id: str, report_data: Dict[str, Any],
                         certificate_files: Dict[str, str] = None,
                         qr_data: Dict[str, Any] = None) -> int:
        """
        Store a generated wipe report and associated files.

        Args:
            session_id: Session identifier
            report_data: Report information from WipeReport
            certificate_files: Dictionary of certificate file paths
            qr_data: QR code data and image path

        Returns:
            Database record ID
        """
        import json
        import time

        # Generate report ID if not provided
        report_id = report_data.get('report_id') or f"BNW-{session_id[:8]}-{int(time.time())}"

        # Prepare report data for database
        db_report = {
            'session_id': session_id,
            'report_id': report_id,
            'device_path': report_data.get('device_path', ''),
            'device_model': report_data.get('device_model', ''),
            'device_serial': report_data.get('device_serial', ''),
            'algorithm_used': report_data.get('algorithm_used', ''),
            'wipe_method': report_data.get('wipe_method', 'software'),
            'start_time': report_data.get('start_time'),
            'end_time': report_data.get('end_time'),
            'total_passes': report_data.get('total_passes', 0),
            'success': report_data.get('success', False),
            'total_bytes_written': report_data.get('total_bytes_written', 0),
            'average_speed_mbps': report_data.get('average_speed_mbps', 0.0),
            'organization': report_data.get('organization', 'BreakNWipe by CodeBreakers'),
            'operator': report_data.get('operator', 'System User'),
            'compliance_standards': report_data.get('compliance_standards', 'NIST SP 800-88')
        }

        # Add certificate file paths if provided
        if certificate_files:
            db_report['certificate_pdf_path'] = certificate_files.get('pdf', '')
            db_report['certificate_json_path'] = certificate_files.get('json', '')

        # Add QR code data if provided
        if qr_data:
            db_report['qr_code_data'] = json.dumps(qr_data)
            db_report['qr_code_image_path'] = qr_data.get('image_path', '')
            db_report['verification_hash'] = qr_data.get('verification_hash', '')

        record_id = self.db.add_wipe_report(db_report)

        logger.info(f"Stored wipe report: session_id={session_id}, report_id={report_id}")
        return record_id

    def get_reports(self, device_path: str = None, limit: int = 100,
                   offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get wipe reports with optional filtering.

        Args:
            device_path: Filter by device path
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of report dictionaries
        """
        return self.db.get_wipe_reports(device_path, limit, offset)

    def get_report_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific report by session ID.

        Args:
            session_id: Session ID to search for

        Returns:
            Report dictionary or None if not found
        """
        return self.db.get_wipe_report(session_id)

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific report by report ID.

        Args:
            report_id: Report ID to search for

        Returns:
            Report dictionary or None if not found
        """
        return self.db.get_wipe_report_by_id(report_id)

    def get_device_reports(self, device_path: str) -> List[Dict[str, Any]]:
        """
        Get all reports for a specific device.

        Args:
            device_path: Device path to filter by

        Returns:
            List of report dictionaries for the device
        """
        return self.db.get_wipe_reports(device_path=device_path, limit=1000)