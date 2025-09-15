"""
BreakNWipe - Comprehensive Data Wiping CLI Utility

A robust, secure, and standards-compliant data wiping solution for IT asset recycling.
Supports multiple algorithms, storage types, and generates tamper-proof certificates.
"""

__version__ = '1.0.0'
__author__ = 'BreakNWipe Development Team'
__email__ = 'contact@breaknwipe.org'
__license__ = 'MIT'

from .wipe_engine import WipeEngine, WipeAlgorithm
from .device import DeviceHandler, StorageDevice
from .certificate import CertificateGenerator, WipeReport

__all__ = [
    'WipeEngine',
    'WipeAlgorithm',
    'DeviceHandler',
    'StorageDevice',
    'CertificateGenerator',
    'WipeReport',
]