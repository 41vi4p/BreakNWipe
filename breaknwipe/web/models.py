"""
Data models for BreakNWipe Web Interface

Pydantic models for API request/response validation and WebSocket communication.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class WipeSessionStatus(str, Enum):
    """Status of a wipe session."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeviceType(str, Enum):
    """Type of storage device."""
    LAPTOP = "laptop"
    MOBILE = "mobile"
    SERVER = "server"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class WipeAlgorithm(str, Enum):
    """Available wiping algorithms."""
    NIST_CLEAR = "nist-clear"
    NIST_PURGE = "nist-purge"
    DOD_3PASS = "dod-3pass"
    DOD_7PASS = "dod-7pass"
    GUTMANN = "gutmann"
    RANDOM = "random"
    ZEROS = "zeros"
    CUSTOM = "custom"

    # Cryptographic Erase Algorithms (REA)
    REA_BASIC = "rea-basic"
    REA_MULTICHAIN = "rea-multichain"
    REA_EXTREME = "rea-extreme"
    REA_FAST = "rea-fast"
    REA_CUSTOM = "rea-custom"


class WipeMode(str, Enum):
    """Wipe mode selection."""
    QUICK = "quick"
    DEEP = "deep"
    ADVANCED = "advanced"


class MobileWipeMode(str, Enum):
    """Mobile device wipe modes."""
    EDL = "edl"
    SP_FLASH = "spflash"
    ODIN = "odin"
    ADB = "adb"


class DeviceInfo(BaseModel):
    """Information about a storage device."""
    path: str = Field(..., description="Device path (e.g., /dev/sda)")
    model: str = Field(..., description="Device model name")
    serial: str = Field(..., description="Device serial number")
    capacity: int = Field(..., description="Device capacity in bytes")
    capacity_human: str = Field(..., description="Human-readable capacity")
    device_type: DeviceType = Field(..., description="Type of device")
    interface: str = Field(..., description="Device interface (SATA, NVMe, etc.)")
    is_mounted: bool = Field(..., description="Whether device is currently mounted")
    secure_erase_support: bool = Field(..., description="Hardware secure erase support")
    mount_points: List[str] = Field(default_factory=list, description="Current mount points, if any")
    is_system_disk: bool = Field(default=False, description="Whether this disk hosts the running system")


class PartitionModel(BaseModel):
    """A single partition and its filesystem, for the drive-health dashboard."""
    path: str
    parent_disk: str
    size_bytes: int
    size_human: str
    fstype: Optional[str] = None
    label: Optional[str] = None
    uuid: Optional[str] = None
    mount_point: Optional[str] = None
    is_mounted: bool = False
    is_system: bool = False
    is_repairable_type: bool = False


class DeviceHealthModel(BaseModel):
    """SMART health/lifespan snapshot for a device, for the drive-health dashboard."""
    smart_overall: Optional[str] = None
    temperature_celsius: Optional[int] = None
    power_on_hours: Optional[int] = None
    power_cycles: Optional[int] = None
    reallocated_sectors: Optional[int] = None
    pending_sectors: Optional[int] = None
    lifespan_remaining_percent: Optional[int] = None
    lifespan_source: str = "not available"
    warnings: List[str] = Field(default_factory=list)


class FsckCheckRequest(BaseModel):
    """Request to check (or, with repair=True, repair) a filesystem."""
    partition: str = Field(..., description="Partition to check, e.g. /dev/sdb1 (not a whole disk)")
    repair: bool = Field(default=False, description="Actually repair; default is check-only and never modifies anything")
    force: bool = Field(default=False, description="Override the system-disk/btrfs repair safety gate (DANGEROUS)")
    filesystem: Optional[str] = Field(default=None, description="Override auto-detected filesystem type")


class ErasureCheckRequest(BaseModel):
    """Request to check whether a device has actually been wiped (read-only)."""
    device: str = Field(..., description="Whole device to check, e.g. /dev/sdb")
    depth: str = Field(default="comprehensive", description="One of: quick, comprehensive, paranoid")


class PartitionResizeRequest(BaseModel):
    """Request to plan (dry-run) or apply a partition resize."""
    partition: str = Field(..., description="Partition to resize, e.g. /dev/sdb1")
    mode: str = Field(..., description="One of: grow, shrink, move")
    target_bytes: Optional[int] = Field(default=None, description="Target size in bytes (shrink); ignored for grow (fills free space)")
    new_start_sector: Optional[int] = Field(default=None, description="New start sector (move)")
    force: bool = Field(default=False, description="Confirm system-disk / experimental-move operations")
    dry_run: bool = Field(default=True, description="Preview the exact commands without touching the disk")


class LvExtendRequest(BaseModel):
    """Request to extend an LVM logical volume (and its filesystem) to fill free VG space."""
    lv_path: str = Field(..., description="Logical volume path, e.g. /dev/ubuntu-vg/ubuntu-lv")


class RecoveryScanRequest(BaseModel):
    """Request to scan a partition for recoverable deleted files (read-only)."""
    partition: str = Field(..., description="Partition to scan, e.g. /dev/sdb1")
    filesystem: Optional[str] = Field(default=None, description="Override auto-detected filesystem type")


class RecoveryRestoreRequest(BaseModel):
    """Request to recover selected deleted files (by inode, via icat) to an output folder on a different device."""
    partition: str = Field(..., description="Partition to recover from, e.g. /dev/sdb1")
    output_dir: str = Field(..., description="Folder to write recovered files to (must be on a different device)")
    inodes: List[str] = Field(default_factory=list, description="Metadata addresses of files to recover (from a scan)")
    filesystem: Optional[str] = Field(default=None, description="Override auto-detected filesystem type")


class RecoveryDeepScanStartRequest(BaseModel):
    """Request to start a background deep-scan (PhotoRec) recovery job."""
    partition: str = Field(..., description="Partition or device to scan, e.g. /dev/sdb1")
    output_dir: str = Field(..., description="Folder to carve recovered files into (must be on a different device)")


class DirEntryModel(BaseModel):
    """A single file or folder entry from the file-shredder's directory browser."""
    name: str
    path: str
    is_dir: bool
    size_bytes: int = 0
    mtime: Optional[float] = None


class DirListingModel(BaseModel):
    """A directory's contents, for the file-shredder's browser."""
    mount_point: str
    path: str
    parent: Optional[str] = None
    entries: List[DirEntryModel] = Field(default_factory=list)


class ShredReliabilityModel(BaseModel):
    """Whether in-place file overwrite can be trusted to destroy data on this partition."""
    partition: str
    fstype: Optional[str] = None
    rotational: Optional[bool] = None
    reliable: bool
    warnings: List[str] = Field(default_factory=list)


class ShredStartRequest(BaseModel):
    """Request to start a file-shredding job: overwrite and delete specific
    files on a mounted partition, leaving the rest of the drive untouched."""
    partition: str = Field(..., description="Mounted partition the files live on, e.g. /dev/sdb1")
    paths: List[str] = Field(..., description="Absolute file paths to shred (as returned by the directory browser)")
    algorithm: WipeAlgorithm = Field(..., description="Overwrite algorithm")
    passes: Optional[int] = Field(default=None, description="Number of passes for the random algorithm")
    encryption_layers: Optional[int] = Field(default=2, description="Number of encryption layers for REA Custom (1-7)")
    overwrite_algorithm: Optional[str] = Field(default="nist-clear", description="Overwrite algorithm for REA Custom")
    fast_mode: Optional[bool] = Field(default=False, description="Use fast mode for REA Custom encryption")


class WipeRequest(BaseModel):
    """Request to start a wipe operation."""
    device_path: str = Field(..., description="Target device path")
    algorithm: WipeAlgorithm = Field(..., description="Wiping algorithm")
    verify: bool = Field(default=True, description="Verify wipe completion")
    generate_certificate: bool = Field(default=True, description="Generate wipe certificate")
    passes: Optional[int] = Field(default=None, description="Number of passes for custom algorithms")
    wipe_mode: Optional[WipeMode] = Field(default=WipeMode.QUICK, description="Wipe mode selection")
    custom_passes: Optional[int] = Field(default=None, description="Custom number of passes")

    # REA Custom Parameters
    encryption_layers: Optional[int] = Field(default=2, description="Number of encryption layers for REA Custom (1-7)")
    overwrite_algorithm: Optional[str] = Field(default="nist-clear", description="Overwrite algorithm for REA Custom")
    fast_mode: Optional[bool] = Field(default=False, description="Use fast mode for REA Custom encryption")


class MobileWipeRequest(BaseModel):
    """Request to start a mobile device wipe operation."""
    device_id: str = Field(..., description="Mobile device identifier")
    wipe_mode: MobileWipeMode = Field(..., description="Mobile wipe mode")
    verify: bool = Field(default=True, description="Verify wipe completion")
    generate_certificate: bool = Field(default=True, description="Generate wipe certificate")


class WipeProgress(BaseModel):
    """Progress information for an ongoing wipe operation."""
    session_id: str = Field(..., description="Unique session identifier")
    status: WipeSessionStatus = Field(..., description="Current status")
    progress_percent: float = Field(..., description="Overall progress percentage")
    current_pass: int = Field(..., description="Current pass number")
    total_passes: int = Field(..., description="Total number of passes")
    speed_mbps: float = Field(..., description="Current wiping speed in MB/s")
    data_processed: int = Field(..., description="Data processed in bytes")
    estimated_remaining: Optional[int] = Field(default=None, description="Estimated time remaining in seconds")
    started_at: datetime = Field(..., description="When the operation started")
    last_updated: datetime = Field(..., description="Last progress update time")


class WipeSession(BaseModel):
    """Complete information about a wipe session."""
    session_id: str = Field(..., description="Unique session identifier")
    device_info: DeviceInfo = Field(..., description="Target device information")
    wipe_request: WipeRequest = Field(..., description="Original wipe request")
    progress: WipeProgress = Field(..., description="Current progress")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    certificate_path: Optional[str] = Field(default=None, description="Path to generated certificate")
    report_id: Optional[str] = Field(default=None, description="Generated report ID for consistency")
    # NOTE: these must be declared here -- WipeSession is a pydantic model, so
    # assigning an undeclared attribute raises. An earlier version set
    # session.qr_data dynamically; that assignment silently failed inside the
    # certificate try/except and aborted report storage every time.
    qr_data: Optional[str] = Field(default=None, description="QR payload JSON generated for the certificate")
    verification_passed: Optional[bool] = Field(default=None, description="Post-wipe verification outcome (None = not run)")
    certificate_files: Optional[Dict[str, Any]] = Field(default=None, description="Generated certificate artifacts (pdf/json/qr_png/blockchain_result)")


class ApiResponse(BaseModel):
    """Standard API response format."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str = Field(..., description="Message type")
    session_id: Optional[str] = Field(default=None, description="Session ID if applicable")
    data: Dict[str, Any] = Field(..., description="Message data")