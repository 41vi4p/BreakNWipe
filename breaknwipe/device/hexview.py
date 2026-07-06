"""
Raw Sector / Hex Viewer Module

Reads raw bytes from a block device at a given offset, read-only. Used to
*see* a drive's contents — most importantly, to visually confirm a wipe
actually zeroed/patterned the device.

Strictly read-only and low-risk: it opens the device with O_RDONLY, never
writes, and bounds every read so a single request can't pull an unbounded
amount into memory. Caller-supplied paths are validated as real block devices
(same helper the destructive modules use). Reading raw devices requires root.
"""

import base64
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

from .filesystem import InvalidDevicePathError, validate_block_device_path

logger = logging.getLogger(__name__)

# Hard cap on a single read so one request can't allocate an unbounded buffer.
MAX_READ_BYTES = 64 * 1024


@dataclass
class SectorData:
    device: str
    offset: int          # byte offset the read started at
    length: int          # number of bytes actually read
    device_size: int     # total device size in bytes (0 if unknown)
    data_base64: str     # the raw bytes, base64-encoded
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "offset": self.offset,
            "length": self.length,
            "device_size": self.device_size,
            "data_base64": self.data_base64,
            "error": self.error,
        }


def device_size_bytes(device_path: str) -> int:
    """Total size of a block device in bytes (via sysfs; 0 if unavailable)."""
    name = os.path.basename(device_path)
    try:
        with open(f"/sys/class/block/{name}/size") as f:
            return int(f.read().strip()) * 512
    except (OSError, ValueError):
        # Fallback: seek to end of the opened device.
        try:
            fd = os.open(device_path, os.O_RDONLY)
            try:
                return os.lseek(fd, 0, os.SEEK_END)
            finally:
                os.close(fd)
        except OSError:
            return 0


def read_sectors(device_path: str, offset: int = 0, length: int = 512) -> SectorData:
    """
    Read `length` bytes from `device_path` starting at byte `offset`, read-only.

    `length` is clamped to MAX_READ_BYTES. Returns a SectorData with the bytes
    base64-encoded plus the device's total size (so a viewer can bound
    navigation). On error (e.g. not root, bad path) `error` is set and
    `data_base64` is empty rather than raising.
    """
    result = SectorData(device=device_path, offset=max(0, offset), length=0, device_size=0, data_base64="")

    try:
        validate_block_device_path(device_path)
    except InvalidDevicePathError as e:
        result.error = str(e)
        return result

    length = max(0, min(int(length), MAX_READ_BYTES))
    offset = max(0, int(offset))
    result.offset = offset

    total = device_size_bytes(device_path)
    result.device_size = total
    if total and offset >= total:
        result.error = f"Offset {offset} is at or past the end of the device ({total} bytes)."
        return result

    try:
        fd = os.open(device_path, os.O_RDONLY)
    except OSError as e:
        result.error = (
            f"Could not open {device_path} for reading: {e}. "
            f"Reading raw devices requires root privileges."
        )
        return result

    try:
        os.lseek(fd, offset, os.SEEK_SET)
        # Read up to `length` bytes; short reads near end-of-device are fine.
        chunks = []
        remaining = length
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    except OSError as e:
        result.error = f"Read failed at offset {offset}: {e}"
        return result
    finally:
        os.close(fd)

    result.length = len(data)
    result.data_base64 = base64.b64encode(data).decode("ascii")
    return result
