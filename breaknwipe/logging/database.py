"""
Database Service for BreakNWipe Logging

Manages SQLite database for storing wipe operation logs and audit trails.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class WipeLogEntry:
    """Data model for wipe operation log entries."""
    id: Optional[int] = None
    session_id: str = ""
    device_path: str = ""
    device_model: str = ""
    device_serial: str = ""
    device_capacity_bytes: int = 0
    device_capacity_human: str = ""
    device_interface: str = ""
    device_type: str = ""
    algorithm_used: str = ""
    total_passes: int = 0
    verification_enabled: bool = False
    certificate_generated: bool = False
    operation_status: str = ""  # pending, running, completed, failed, cancelled
    progress_percent: float = 0.0
    data_processed_bytes: int = 0
    average_speed_mbps: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: int = 0
    error_message: Optional[str] = None
    operator: str = "System User"
    organization: str = "BreakNWipe by CodeBreakers"
    certificate_path: Optional[str] = None
    report_id: Optional[str] = None
    compliance_standards: str = "NIST SP 800-88"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LoggingDatabase:
    """SQLite database manager for wipe operation logs."""

    def __init__(self, db_path: str = None):
        """
        Initialize the logging database.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            # Default to user's home directory
            db_dir = Path.home() / ".breaknwipe"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "logs.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")

            # Create wipe_logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wipe_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    device_path TEXT NOT NULL,
                    device_model TEXT,
                    device_serial TEXT,
                    device_capacity_bytes INTEGER,
                    device_capacity_human TEXT,
                    device_interface TEXT,
                    device_type TEXT,
                    algorithm_used TEXT,
                    total_passes INTEGER,
                    verification_enabled BOOLEAN,
                    certificate_generated BOOLEAN,
                    operation_status TEXT NOT NULL,
                    progress_percent REAL DEFAULT 0.0,
                    data_processed_bytes INTEGER DEFAULT 0,
                    average_speed_mbps REAL DEFAULT 0.0,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_seconds INTEGER DEFAULT 0,
                    error_message TEXT,
                    operator TEXT DEFAULT 'System User',
                    organization TEXT DEFAULT 'BreakNWipe by CodeBreakers',
                    certificate_path TEXT,
                    report_id TEXT,
                    compliance_standards TEXT DEFAULT 'NIST SP 800-88',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create device_history table for tracking device-specific operations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_path TEXT NOT NULL,
                    device_model TEXT,
                    device_serial TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_wipe TIMESTAMP,
                    total_wipes INTEGER DEFAULT 0,
                    last_algorithm TEXT,
                    last_status TEXT,
                    notes TEXT
                )
            """)

            # Create audit_trail table for system events
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    event_description TEXT,
                    event_data TEXT,  -- JSON data
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_agent TEXT,
                    ip_address TEXT
                )
            """)

            # Create reports table for storing generated certificates and QR codes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wipe_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    report_id TEXT UNIQUE NOT NULL,
                    device_path TEXT NOT NULL,
                    device_model TEXT,
                    device_serial TEXT,
                    algorithm_used TEXT,
                    wipe_method TEXT DEFAULT 'software',
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_passes INTEGER,
                    success BOOLEAN,
                    total_bytes_written INTEGER,
                    average_speed_mbps REAL,
                    organization TEXT DEFAULT 'BreakNWipe by CodeBreakers',
                    operator TEXT DEFAULT 'System User',
                    compliance_standards TEXT DEFAULT 'NIST SP 800-88',
                    certificate_pdf_path TEXT,
                    certificate_json_path TEXT,
                    qr_code_data TEXT,  -- JSON containing QR code info
                    qr_code_image_path TEXT,
                    verification_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES wipe_logs(session_id)
                )
            """)

            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wipe_logs_device_path ON wipe_logs(device_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wipe_logs_status ON wipe_logs(operation_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wipe_logs_created_at ON wipe_logs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_device_history_path ON device_history(device_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_session ON audit_trail(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_session ON wipe_reports(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_device_path ON wipe_reports(device_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON wipe_reports(created_at)")

            conn.commit()

    def add_wipe_log(self, log_entry: WipeLogEntry) -> int:
        """
        Add a new wipe log entry.

        Args:
            log_entry: WipeLogEntry object

        Returns:
            ID of the inserted record
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Convert dataclass to dict, handling datetime objects
            data = asdict(log_entry)
            data.pop('id', None)  # Remove id field for insertion

            # Convert datetime objects to ISO strings
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif value is None:
                    data[key] = None

            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])

            cursor = conn.execute(
                f"INSERT INTO wipe_logs ({columns}) VALUES ({placeholders})",
                list(data.values())
            )

            log_id = cursor.lastrowid

            # Update device history
            self._update_device_history(conn, log_entry)

            return log_id

    def update_wipe_log(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing wipe log entry.

        Args:
            session_id: Session ID of the log to update
            updates: Dictionary of fields to update

        Returns:
            True if update was successful
        """
        with sqlite3.connect(self.db_path) as conn:
            # Add updated_at timestamp
            updates['updated_at'] = datetime.now().isoformat()

            # Convert datetime objects to ISO strings
            for key, value in updates.items():
                if isinstance(value, datetime):
                    updates[key] = value.isoformat()

            set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [session_id]

            cursor = conn.execute(
                f"UPDATE wipe_logs SET {set_clause} WHERE session_id = ?",
                values
            )

            return cursor.rowcount > 0

    def get_wipe_log(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific wipe log by session ID.

        Args:
            session_id: Session ID to search for

        Returns:
            Dictionary with log data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                "SELECT * FROM wipe_logs WHERE session_id = ?",
                (session_id,)
            )

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_wipe_logs(self,
                     device_path: str = None,
                     status: str = None,
                     limit: int = 100,
                     offset: int = 0,
                     order_by: str = "created_at DESC") -> List[Dict[str, Any]]:
        """
        Get wipe logs with optional filtering.

        Args:
            device_path: Filter by device path
            status: Filter by operation status
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: SQL ORDER BY clause

        Returns:
            List of log dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM wipe_logs"
            params = []
            conditions = []

            if device_path:
                conditions.append("device_path = ?")
                params.append(device_path)

            if status:
                conditions.append("operation_status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_device_history(self, device_path: str = None) -> List[Dict[str, Any]]:
        """
        Get device history records.

        Args:
            device_path: Specific device path, or None for all devices

        Returns:
            List of device history dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if device_path:
                cursor = conn.execute(
                    "SELECT * FROM device_history WHERE device_path = ?",
                    (device_path,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM device_history ORDER BY last_wipe DESC"
                )

            return [dict(row) for row in cursor.fetchall()]

    def add_audit_event(self, session_id: str, event_type: str,
                       description: str, event_data: Dict[str, Any] = None,
                       user_agent: str = None, ip_address: str = None):
        """
        Add an audit trail event.

        Args:
            session_id: Associated session ID
            event_type: Type of event (e.g., 'wipe_started', 'wipe_cancelled')
            description: Human-readable description
            event_data: Additional structured data
            user_agent: User agent string
            ip_address: Client IP address
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_trail
                (session_id, event_type, event_description, event_data, user_agent, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                event_type,
                description,
                json.dumps(event_data) if event_data else None,
                user_agent,
                ip_address
            ))

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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute("""
                    SELECT * FROM audit_trail
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM audit_trail
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def _update_device_history(self, conn: sqlite3.Connection, log_entry: WipeLogEntry):
        """Update device history table."""
        # Check if device exists in history
        cursor = conn.execute(
            "SELECT id, total_wipes FROM device_history WHERE device_path = ?",
            (log_entry.device_path,)
        )

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            conn.execute("""
                UPDATE device_history
                SET last_wipe = ?, total_wipes = ?, last_algorithm = ?, last_status = ?
                WHERE device_path = ?
            """, (
                datetime.now().isoformat(),
                existing[1] + 1,
                log_entry.algorithm_used,
                log_entry.operation_status,
                log_entry.device_path
            ))
        else:
            # Insert new device record
            conn.execute("""
                INSERT INTO device_history
                (device_path, device_model, device_serial, last_wipe, total_wipes, last_algorithm, last_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                log_entry.device_path,
                log_entry.device_model,
                log_entry.device_serial,
                datetime.now().isoformat(),
                1,
                log_entry.algorithm_used,
                log_entry.operation_status
            ))

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            stats = {}

            # Total operations
            cursor = conn.execute("SELECT COUNT(*) as total FROM wipe_logs")
            stats['total_operations'] = cursor.fetchone()[0]

            # Operations by status
            cursor = conn.execute("""
                SELECT operation_status, COUNT(*) as count
                FROM wipe_logs
                GROUP BY operation_status
            """)
            stats['operations_by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Total devices
            cursor = conn.execute("SELECT COUNT(*) as total FROM device_history")
            stats['total_devices'] = cursor.fetchone()[0]

            # Recent activity (last 30 days)
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM wipe_logs
                WHERE created_at >= datetime('now', '-30 days')
            """)
            stats['recent_operations'] = cursor.fetchone()[0]

            return stats

    def add_wipe_report(self, report_data: Dict[str, Any]) -> int:
        """
        Add a generated wipe report to the database.

        Args:
            report_data: Dictionary containing report information

        Returns:
            ID of the inserted record
        """
        with sqlite3.connect(self.db_path) as conn:
            # Convert datetime objects to ISO strings
            for key, value in report_data.items():
                if isinstance(value, datetime):
                    report_data[key] = value.isoformat()

            columns = ', '.join(report_data.keys())
            placeholders = ', '.join(['?' for _ in report_data])

            cursor = conn.execute(
                f"INSERT INTO wipe_reports ({columns}) VALUES ({placeholders})",
                list(report_data.values())
            )

            return cursor.lastrowid

    def get_wipe_reports(self, device_path: str = None, limit: int = 100,
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM wipe_reports"
            params = []

            if device_path:
                query += " WHERE device_path = ?"
                params.append(device_path)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_wipe_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific wipe report by session ID.

        Args:
            session_id: Session ID to search for

        Returns:
            Dictionary with report data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                "SELECT * FROM wipe_reports WHERE session_id = ?",
                (session_id,)
            )

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_wipe_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific wipe report by report ID.

        Args:
            report_id: Report ID to search for

        Returns:
            Dictionary with report data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                "SELECT * FROM wipe_reports WHERE report_id = ?",
                (report_id,)
            )

            row = cursor.fetchone()
            return dict(row) if row else None

    def update_wipe_report(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing wipe report.

        Args:
            session_id: Session ID of the report to update
            updates: Dictionary of fields to update

        Returns:
            True if update was successful
        """
        with sqlite3.connect(self.db_path) as conn:
            # Add updated_at timestamp
            updates['updated_at'] = datetime.now().isoformat()

            # Convert datetime objects to ISO strings
            for key, value in updates.items():
                if isinstance(value, datetime):
                    updates[key] = value.isoformat()

            set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [session_id]

            cursor = conn.execute(
                f"UPDATE wipe_reports SET {set_clause} WHERE session_id = ?",
                values
            )

            return cursor.rowcount > 0