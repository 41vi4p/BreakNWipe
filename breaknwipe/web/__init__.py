"""
BreakNWipe Web Interface Module

FastAPI-based web interface for the BreakNWipe data wiping utility.
Provides a modern web GUI with real-time progress tracking.
"""

from .server import WebServer
from .models import WipeSessionStatus, DeviceInfo, WipeProgress

__all__ = [
    'WebServer',
    'WipeSessionStatus',
    'DeviceInfo',
    'WipeProgress'
]