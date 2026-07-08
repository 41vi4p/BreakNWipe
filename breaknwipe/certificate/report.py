"""
Wipe Report Data Models

Data models for wipe operation reports and certificates.
"""

import time
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from .. import __version__


class ReportFormat(Enum):
    """Supported report formats."""
    PDF = "pdf"
    JSON = "json"
    XML = "xml"
    HTML = "html"


@dataclass
class DeviceInfo:
    """Device information for report."""
    path: str
    model: str
    serial: str
    capacity_bytes: int
    capacity_human: str
    device_type: str
    interface: str
    vendor: Optional[str] = None
    firmware_version: Optional[str] = None
    wwn: Optional[str] = None
    # Hidden area detection
    hidden_capacity_bytes: Optional[int] = None
    hidden_sectors: Optional[int] = None
    hpa_detected: Optional[bool] = None
    dco_detected: Optional[bool] = None
    capacity_breakdown: Optional[Dict[str, Any]] = None


@dataclass
class WipePassResult:
    """Result of a single wipe pass."""
    pass_number: int
    algorithm: str
    pattern_description: str
    start_time: float
    end_time: float
    bytes_written: int
    success: bool
    verification_hash: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of wipe verification."""
    verification_type: str
    passed: bool
    entropy_score: Optional[float] = None
    pattern_detection_rate: Optional[float] = None
    sample_count: int = 0
    notes: Optional[str] = None


@dataclass
class WipeReport:
    """Complete wipe operation report."""

    # Report metadata
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_version: str = "1.0"
    generated_at: float = field(default_factory=time.time)

    # Organization and operator info
    organization: Optional[str] = None
    operator: Optional[str] = None
    location: Optional[str] = None

    # Device information
    device_info: Optional[DeviceInfo] = None

    # Wipe operation details
    algorithm_used: Optional[str] = None
    wipe_method: Optional[str] = None  # "software", "hardware", "hybrid"
    start_time: float = 0
    end_time: float = 0
    total_passes: int = 0

    # Results
    success: bool = False
    pass_results: List[WipePassResult] = field(default_factory=list)
    verification_result: Optional[VerificationResult] = None

    # Performance metrics
    total_bytes_written: int = 0
    average_speed_mbps: float = 0
    peak_temperature_celsius: Optional[int] = None

    # Compliance and standards
    standards_compliance: List[str] = field(default_factory=list)
    certificate_level: str = "standard"  # "basic", "standard", "enhanced"

    # Security and verification
    digital_signature: Optional[str] = None
    signature_algorithm: str = "RSA-2048"
    certificate_hash: Optional[str] = None

    # Additional metadata
    software_version: str = field(default_factory=lambda: __version__)
    system_info: Dict[str, Any] = field(default_factory=dict)
    environment_info: Dict[str, Any] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization processing."""
        if self.start_time > 0 and self.end_time > 0:
            duration = self.end_time - self.start_time
            if duration > 0 and self.total_bytes_written > 0:
                self.average_speed_mbps = (self.total_bytes_written / (1024 * 1024)) / duration

    @property
    def duration_seconds(self) -> int:
        """Get operation duration in seconds."""
        return int(self.end_time - self.start_time) if self.end_time > self.start_time else 0

    @property
    def duration_human(self) -> str:
        """Get human-readable duration."""
        duration = self.duration_seconds
        if duration < 60:
            return f"{duration}s"
        elif duration < 3600:
            return f"{duration // 60}m {duration % 60}s"
        else:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            return f"{hours}h {minutes}m"

    @property
    def success_status(self) -> str:
        """Get human-readable success status."""
        if self.success:
            if self.verification_result and self.verification_result.passed:
                return "PASSED (Verified)"
            else:
                return "PASSED"
        else:
            return "FAILED"

    @property
    def compliance_status(self) -> str:
        """Get compliance status string."""
        if self.standards_compliance:
            return ", ".join(self.standards_compliance)
        else:
            return "No specific standard"

    def add_pass_result(self, pass_result: WipePassResult):
        """Add a pass result to the report."""
        self.pass_results.append(pass_result)
        self.total_bytes_written += pass_result.bytes_written

        # Update total passes
        self.total_passes = len(self.pass_results)

    def set_verification_result(self, verification: VerificationResult):
        """Set verification result."""
        self.verification_result = verification

    def calculate_report_hash(self) -> str:
        """Calculate SHA-256 hash of core report data."""
        # Create a string of core report data for hashing
        core_data = (
            f"{self.report_id}{self.device_info.serial if self.device_info else ''}"
            f"{self.algorithm_used}{self.start_time}{self.end_time}"
            f"{self.total_bytes_written}{self.success}"
        )

        # Add pass results
        for pass_result in self.pass_results:
            core_data += f"{pass_result.pass_number}{pass_result.bytes_written}{pass_result.success}"

        # Add verification result
        if self.verification_result:
            core_data += f"{self.verification_result.passed}{self.verification_result.verification_type}"

        # Calculate hash
        hash_obj = hashlib.sha256(core_data.encode('utf-8'))
        return hash_obj.hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            'report_metadata': {
                'report_id': self.report_id,
                'report_version': self.report_version,
                'generated_at': self.generated_at,
                'generated_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.generated_at))
            },
            'organization_info': {
                'organization': self.organization,
                'operator': self.operator,
                'location': self.location
            },
            'device_info': {
                'path': self.device_info.path if self.device_info else None,
                'model': self.device_info.model if self.device_info else None,
                'serial': self.device_info.serial if self.device_info else None,
                'capacity_bytes': self.device_info.capacity_bytes if self.device_info else None,
                'capacity_human': self.device_info.capacity_human if self.device_info else None,
                'device_type': self.device_info.device_type if self.device_info else None,
                'interface': self.device_info.interface if self.device_info else None,
                'vendor': self.device_info.vendor if self.device_info else None,
                'firmware_version': self.device_info.firmware_version if self.device_info else None,
                'wwn': self.device_info.wwn if self.device_info else None,
                'hidden_capacity_bytes': self.device_info.hidden_capacity_bytes if self.device_info else None,
                'hidden_sectors': self.device_info.hidden_sectors if self.device_info else None,
                'hpa_detected': self.device_info.hpa_detected if self.device_info else None,
                'dco_detected': self.device_info.dco_detected if self.device_info else None,
                'capacity_breakdown': self.device_info.capacity_breakdown if self.device_info else None
            },
            'wipe_operation': {
                'algorithm_used': self.algorithm_used,
                'wipe_method': self.wipe_method,
                'start_time': self.start_time,
                'start_time_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.start_time)),
                'end_time': self.end_time,
                'end_time_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.end_time)),
                'duration_seconds': self.duration_seconds,
                'duration_human': self.duration_human,
                'total_passes': self.total_passes
            },
            'results': {
                'success': self.success,
                'success_status': self.success_status,
                'total_bytes_written': self.total_bytes_written,
                'average_speed_mbps': round(self.average_speed_mbps, 2),
                'peak_temperature_celsius': self.peak_temperature_celsius,
                'pass_results': [
                    {
                        'pass_number': pr.pass_number,
                        'algorithm': pr.algorithm,
                        'pattern_description': pr.pattern_description,
                        'start_time': pr.start_time,
                        'end_time': pr.end_time,
                        'duration_seconds': int(pr.end_time - pr.start_time),
                        'bytes_written': pr.bytes_written,
                        'success': pr.success,
                        'verification_hash': pr.verification_hash,
                        'error_message': pr.error_message
                    }
                    for pr in self.pass_results
                ]
            },
            'verification': {
                'verification_type': self.verification_result.verification_type if self.verification_result else None,
                'passed': self.verification_result.passed if self.verification_result else None,
                'entropy_score': self.verification_result.entropy_score if self.verification_result else None,
                'pattern_detection_rate': self.verification_result.pattern_detection_rate if self.verification_result else None,
                'sample_count': self.verification_result.sample_count if self.verification_result else None,
                'notes': self.verification_result.notes if self.verification_result else None
            },
            'compliance': {
                'standards_compliance': self.standards_compliance,
                'compliance_status': self.compliance_status,
                'certificate_level': self.certificate_level
            },
            'security': {
                'digital_signature': self.digital_signature,
                'signature_algorithm': self.signature_algorithm,
                'certificate_hash': self.certificate_hash or self.calculate_report_hash()
            },
            'system_info': {
                'software_version': self.software_version,
                'system_info': self.system_info,
                'environment_info': self.environment_info
            },
            'custom_fields': self.custom_fields
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WipeReport':
        """Create WipeReport from dictionary."""
        report = cls()

        # Report metadata
        metadata = data.get('report_metadata', {})
        report.report_id = metadata.get('report_id', str(uuid.uuid4()))
        report.report_version = metadata.get('report_version', '1.0')
        report.generated_at = metadata.get('generated_at', time.time())

        # Organization info
        org_info = data.get('organization_info', {})
        report.organization = org_info.get('organization')
        report.operator = org_info.get('operator')
        report.location = org_info.get('location')

        # Device info
        device_data = data.get('device_info', {})
        if device_data.get('path'):
            report.device_info = DeviceInfo(
                path=device_data['path'],
                model=device_data.get('model', 'Unknown'),
                serial=device_data.get('serial', 'Unknown'),
                capacity_bytes=device_data.get('capacity_bytes', 0),
                capacity_human=device_data.get('capacity_human', '0 B'),
                device_type=device_data.get('device_type', 'unknown'),
                interface=device_data.get('interface', 'unknown'),
                vendor=device_data.get('vendor'),
                firmware_version=device_data.get('firmware_version'),
                wwn=device_data.get('wwn'),
                hidden_capacity_bytes=device_data.get('hidden_capacity_bytes'),
                hidden_sectors=device_data.get('hidden_sectors'),
                hpa_detected=device_data.get('hpa_detected'),
                dco_detected=device_data.get('dco_detected'),
                capacity_breakdown=device_data.get('capacity_breakdown')
            )

        # Wipe operation
        wipe_data = data.get('wipe_operation', {})
        report.algorithm_used = wipe_data.get('algorithm_used')
        report.wipe_method = wipe_data.get('wipe_method')
        report.start_time = wipe_data.get('start_time', 0)
        report.end_time = wipe_data.get('end_time', 0)
        report.total_passes = wipe_data.get('total_passes', 0)

        # Results
        results_data = data.get('results', {})
        report.success = results_data.get('success', False)
        report.total_bytes_written = results_data.get('total_bytes_written', 0)
        report.average_speed_mbps = results_data.get('average_speed_mbps', 0)
        report.peak_temperature_celsius = results_data.get('peak_temperature_celsius')

        # Pass results
        for pass_data in results_data.get('pass_results', []):
            pass_result = WipePassResult(
                pass_number=pass_data['pass_number'],
                algorithm=pass_data['algorithm'],
                pattern_description=pass_data['pattern_description'],
                start_time=pass_data['start_time'],
                end_time=pass_data['end_time'],
                bytes_written=pass_data['bytes_written'],
                success=pass_data['success'],
                verification_hash=pass_data.get('verification_hash'),
                error_message=pass_data.get('error_message')
            )
            report.pass_results.append(pass_result)

        # Verification
        verification_data = data.get('verification', {})
        if verification_data.get('verification_type'):
            report.verification_result = VerificationResult(
                verification_type=verification_data['verification_type'],
                passed=verification_data.get('passed', False),
                entropy_score=verification_data.get('entropy_score'),
                pattern_detection_rate=verification_data.get('pattern_detection_rate'),
                sample_count=verification_data.get('sample_count', 0),
                notes=verification_data.get('notes')
            )

        # Compliance
        compliance_data = data.get('compliance', {})
        report.standards_compliance = compliance_data.get('standards_compliance', [])
        report.certificate_level = compliance_data.get('certificate_level', 'standard')

        # Security
        security_data = data.get('security', {})
        report.digital_signature = security_data.get('digital_signature')
        report.signature_algorithm = security_data.get('signature_algorithm', 'RSA-2048')
        report.certificate_hash = security_data.get('certificate_hash')

        # System info
        system_data = data.get('system_info', {})
        # Deliberately NOT defaulted to the current version: when re-loading an
        # uploaded/old report for verification, claiming today's version would
        # misrepresent what actually generated it.
        report.software_version = system_data.get('software_version', 'unknown')
        report.system_info = system_data.get('system_info', {})
        report.environment_info = system_data.get('environment_info', {})

        # Custom fields
        report.custom_fields = data.get('custom_fields', {})

        return report

    def get_summary(self) -> str:
        """Get a brief summary of the wipe operation."""
        device_desc = "Unknown Device"
        if self.device_info:
            device_desc = f"{self.device_info.model} ({self.device_info.capacity_human})"

        return (f"{self.success_status} - {device_desc} - "
               f"{self.algorithm_used} - {self.duration_human} - "
               f"{self.compliance_status}")

    def validate(self) -> List[str]:
        """Validate report completeness and return list of issues."""
        issues = []

        if not self.device_info:
            issues.append("Device information missing")
        elif not self.device_info.serial:
            issues.append("Device serial number missing")

        if not self.algorithm_used:
            issues.append("Wipe algorithm not specified")

        if self.start_time == 0 or self.end_time == 0:
            issues.append("Operation timestamps missing")

        if not self.pass_results:
            issues.append("No wipe pass results recorded")

        if self.success and not self.verification_result:
            issues.append("Successful wipe should include verification results")

        return issues