"""
BreakNWipe - Comprehensive Data Wiping CLI Utility

A robust, secure, and standards-compliant data wiping solution for IT asset recycling.
Supports multiple algorithms, storage types, and generates tamper-proof certificates.

Developed by CodeBreakers Team:
- David Porathur
- Blaise Rodrigues
- Vanessa Rodrigues
- Natasha Lewis
- Chris Lopes
- Anastasia Lopes
"""

__version__ = '3.1.0'
__author__ = 'CodeBreakers Team'
__email__ = 'contact@breaknwipe.org'
__license__ = 'GPL-3.0-or-later'
__credits__ = [
    'David Porathur',
    'Blaise Rodrigues',
    'Vanessa Rodrigues',
    'Natasha Lewis',
    'Chris Lopes',
    'Anastasia Lopes'
]

# Load environment variables for blockchain integration
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not available, environment variables should be set manually
    pass

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