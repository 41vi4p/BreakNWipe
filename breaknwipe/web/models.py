"""
Data models for BreakNWipe Web Interface

Pydantic models for API request/response validation and WebSocket communication.
"""

from enum import Enum
from typing import Optional, Dict, Any
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


class WipeRequest(BaseModel):
    """Request to start a wipe operation."""
    device_path: str = Field(..., description="Target device path")
    algorithm: WipeAlgorithm = Field(..., description="Wiping algorithm")
    verify: bool = Field(default=True, description="Verify wipe completion")
    generate_certificate: bool = Field(default=True, description="Generate wipe certificate")
    passes: Optional[int] = Field(default=None, description="Number of passes for custom algorithms")
    wipe_mode: Optional[WipeMode] = Field(default=WipeMode.QUICK, description="Wipe mode selection")
    custom_passes: Optional[int] = Field(default=None, description="Custom number of passes")


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