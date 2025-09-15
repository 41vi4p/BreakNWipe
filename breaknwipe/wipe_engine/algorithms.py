"""
Data Wiping Algorithms

Implementation of various secure data wiping algorithms including
NIST SP 800-88, DoD 5220.22-M, Gutmann Method, and others.
"""

import os
import random
import logging
from enum import Enum
from typing import List, Generator, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AlgorithmType(Enum):
    """Enumeration of supported wiping algorithms."""
    NIST_CLEAR = "nist-clear"
    NIST_PURGE = "nist-purge"
    DOD_3PASS = "dod-3pass"
    DOD_7PASS = "dod-7pass"
    GUTMANN = "gutmann"
    RANDOM = "random"
    ZEROS = "zeros"
    CUSTOM = "custom"


@dataclass
class WipePass:
    """Represents a single wipe pass with its pattern and description."""
    pass_number: int
    pattern: bytes
    description: str
    verify: bool = True


class WipeAlgorithm:
    """Base class for all wiping algorithms."""

    def __init__(self, algorithm_type: AlgorithmType, block_size: int = 65536):
        """
        Initialize wipe algorithm.

        Args:
            algorithm_type: Type of algorithm to use
            block_size: Size of data blocks to write (default 64KB)
        """
        self.algorithm_type = algorithm_type
        self.block_size = block_size
        self._passes: List[WipePass] = []
        self._setup_passes()

    def _setup_passes(self):
        """Setup the wipe passes based on algorithm type."""
        if self.algorithm_type == AlgorithmType.NIST_CLEAR:
            self._setup_nist_clear()
        elif self.algorithm_type == AlgorithmType.NIST_PURGE:
            self._setup_nist_purge()
        elif self.algorithm_type == AlgorithmType.DOD_3PASS:
            self._setup_dod_3pass()
        elif self.algorithm_type == AlgorithmType.DOD_7PASS:
            self._setup_dod_7pass()
        elif self.algorithm_type == AlgorithmType.GUTMANN:
            self._setup_gutmann()
        elif self.algorithm_type == AlgorithmType.RANDOM:
            self._setup_random()
        elif self.algorithm_type == AlgorithmType.ZEROS:
            self._setup_zeros()

    def _setup_nist_clear(self):
        """Setup NIST SP 800-88 Clear method (single pass)."""
        self._passes = [
            WipePass(1, b'\\x00' * self.block_size, "NIST Clear - Zero fill")
        ]

    def _setup_nist_purge(self):
        """Setup NIST SP 800-88 Purge method (3 passes)."""
        self._passes = [
            WipePass(1, b'\\x00' * self.block_size, "NIST Purge Pass 1 - Zeros"),
            WipePass(2, b'\\xFF' * self.block_size, "NIST Purge Pass 2 - Ones"),
            WipePass(3, self._generate_random_block(), "NIST Purge Pass 3 - Random")
        ]

    def _setup_dod_3pass(self):
        """Setup DoD 5220.22-M 3-pass method."""
        self._passes = [
            WipePass(1, b'\\x00' * self.block_size, "DoD Pass 1 - Write zeros"),
            WipePass(2, b'\\xFF' * self.block_size, "DoD Pass 2 - Write ones"),
            WipePass(3, self._generate_random_block(), "DoD Pass 3 - Write random", verify=True)
        ]

    def _setup_dod_7pass(self):
        """Setup DoD 5220.22-M 7-pass enhanced method."""
        # First 3-pass cycle
        self._passes.extend([
            WipePass(1, b'\\x00' * self.block_size, "DoD 7-Pass 1 - Zeros"),
            WipePass(2, b'\\xFF' * self.block_size, "DoD 7-Pass 2 - Ones"),
            WipePass(3, self._generate_random_block(), "DoD 7-Pass 3 - Random"),
        ])
        # Second 3-pass cycle
        self._passes.extend([
            WipePass(4, b'\\x00' * self.block_size, "DoD 7-Pass 4 - Zeros"),
            WipePass(5, b'\\xFF' * self.block_size, "DoD 7-Pass 5 - Ones"),
            WipePass(6, self._generate_random_block(), "DoD 7-Pass 6 - Random"),
        ])
        # Final random pass with verification
        self._passes.append(
            WipePass(7, self._generate_random_block(), "DoD 7-Pass 7 - Final Random", verify=True)
        )

    def _setup_gutmann(self):
        """Setup Gutmann 35-pass method."""
        # First 4 random passes
        for i in range(1, 5):
            self._passes.append(
                WipePass(i, self._generate_random_block(), f"Gutmann Pass {i} - Random")
            )

        # 27 specific patterns for different encoding schemes
        gutmann_patterns = [
            b'\\x55', b'\\xAA', b'\\x92\\x49\\x24', b'\\x49\\x24\\x92',
            b'\\x24\\x92\\x49', b'\\x00', b'\\x11', b'\\x22', b'\\x33',
            b'\\x44', b'\\x55', b'\\x66', b'\\x77', b'\\x88', b'\\x99',
            b'\\xAA', b'\\xBB', b'\\xCC', b'\\xDD', b'\\xEE', b'\\xFF',
            b'\\x92\\x49\\x24', b'\\x49\\x24\\x92', b'\\x24\\x92\\x49',
            b'\\x6D\\xB6\\xDB', b'\\xB6\\xDB\\x6D', b'\\xDB\\x6D\\xB6'
        ]

        for i, pattern in enumerate(gutmann_patterns, 5):
            # Repeat pattern to fill block
            repeated_pattern = pattern * (self.block_size // len(pattern) + 1)
            self._passes.append(
                WipePass(i, repeated_pattern[:self.block_size],
                        f"Gutmann Pass {i} - Pattern {pattern.hex()}")
            )

        # Final 4 random passes
        for i in range(32, 36):
            self._passes.append(
                WipePass(i, self._generate_random_block(),
                        f"Gutmann Pass {i} - Final Random")
            )

    def _setup_random(self, passes: int = 3):
        """Setup random data wiping with configurable passes."""
        for i in range(1, passes + 1):
            self._passes.append(
                WipePass(i, self._generate_random_block(),
                        f"Random Pass {i}")
            )

    def _setup_zeros(self):
        """Setup single-pass zero fill."""
        self._passes = [
            WipePass(1, b'\\x00' * self.block_size, "Zero Fill")
        ]

    def _generate_random_block(self) -> bytes:
        """Generate a block of cryptographically secure random data."""
        return os.urandom(self.block_size)

    def get_passes(self) -> List[WipePass]:
        """Get list of wipe passes for this algorithm."""
        return self._passes.copy()

    def get_total_passes(self) -> int:
        """Get total number of passes for this algorithm."""
        return len(self._passes)

    def get_description(self) -> str:
        """Get human-readable description of the algorithm."""
        descriptions = {
            AlgorithmType.NIST_CLEAR: "NIST SP 800-88 Clear (1 pass)",
            AlgorithmType.NIST_PURGE: "NIST SP 800-88 Purge (3 passes)",
            AlgorithmType.DOD_3PASS: "DoD 5220.22-M Standard (3 passes)",
            AlgorithmType.DOD_7PASS: "DoD 5220.22-M Enhanced (7 passes)",
            AlgorithmType.GUTMANN: "Gutmann Method (35 passes)",
            AlgorithmType.RANDOM: f"Random Data ({len(self._passes)} passes)",
            AlgorithmType.ZEROS: "Zero Fill (1 pass)",
            AlgorithmType.CUSTOM: f"Custom Algorithm ({len(self._passes)} passes)"
        }
        return descriptions.get(self.algorithm_type, "Unknown Algorithm")

    def is_secure_for_ssd(self) -> bool:
        """Check if algorithm is appropriate for SSDs."""
        # SSDs benefit from fewer, larger passes due to wear leveling
        secure_for_ssd = {
            AlgorithmType.NIST_CLEAR: True,
            AlgorithmType.NIST_PURGE: True,
            AlgorithmType.DOD_3PASS: True,
            AlgorithmType.DOD_7PASS: False,  # Too many passes
            AlgorithmType.GUTMANN: False,    # Designed for HDDs
            AlgorithmType.RANDOM: True,      # Depends on pass count
            AlgorithmType.ZEROS: True,
            AlgorithmType.CUSTOM: True       # User responsibility
        }
        return secure_for_ssd.get(self.algorithm_type, False)

    def estimate_time(self, device_size_bytes: int, write_speed_mbps: int) -> int:
        """
        Estimate completion time in seconds.

        Args:
            device_size_bytes: Size of device to wipe
            write_speed_mbps: Write speed in MB/s

        Returns:
            Estimated time in seconds
        """
        total_bytes = device_size_bytes * self.get_total_passes()
        seconds = total_bytes / (write_speed_mbps * 1024 * 1024)
        return int(seconds)


class CustomWipeAlgorithm(WipeAlgorithm):
    """Custom wiping algorithm with user-defined patterns."""

    def __init__(self, passes: List[bytes], block_size: int = 65536):
        """
        Initialize custom algorithm.

        Args:
            passes: List of byte patterns for each pass
            block_size: Size of data blocks to write
        """
        self.algorithm_type = AlgorithmType.CUSTOM
        self.block_size = block_size
        self._passes = []

        for i, pattern in enumerate(passes, 1):
            # Repeat pattern to fill block size
            if len(pattern) < block_size:
                repeated = pattern * (block_size // len(pattern) + 1)
                pattern = repeated[:block_size]

            self._passes.append(
                WipePass(i, pattern, f"Custom Pass {i}")
            )


def create_algorithm(algorithm_type: str, **kwargs) -> WipeAlgorithm:
    """
    Factory function to create wipe algorithms.

    Args:
        algorithm_type: String identifier for algorithm type
        **kwargs: Additional parameters (e.g., passes for random algorithm)

    Returns:
        Configured WipeAlgorithm instance
    """
    try:
        algo_enum = AlgorithmType(algorithm_type)
    except ValueError:
        raise ValueError(f"Unsupported algorithm type: {algorithm_type}")

    if algo_enum == AlgorithmType.RANDOM:
        passes = kwargs.get('passes', 3)
        algorithm = WipeAlgorithm(algo_enum)
        algorithm._setup_random(passes)
        return algorithm

    return WipeAlgorithm(algo_enum)


def list_available_algorithms() -> List[dict]:
    """
    Get list of available algorithms with metadata.

    Returns:
        List of algorithm information dictionaries
    """
    algorithms = []

    for algo_type in AlgorithmType:
        algorithm = WipeAlgorithm(algo_type)
        algorithms.append({
            'type': algo_type.value,
            'name': algorithm.get_description(),
            'passes': algorithm.get_total_passes(),
            'ssd_safe': algorithm.is_secure_for_ssd(),
            'category': _get_algorithm_category(algo_type)
        })

    return algorithms


def _get_algorithm_category(algo_type: AlgorithmType) -> str:
    """Get category for algorithm type."""
    categories = {
        AlgorithmType.NIST_CLEAR: "Standards Compliant",
        AlgorithmType.NIST_PURGE: "Standards Compliant",
        AlgorithmType.DOD_3PASS: "Government Standard",
        AlgorithmType.DOD_7PASS: "Government Standard",
        AlgorithmType.GUTMANN: "Academic Research",
        AlgorithmType.RANDOM: "General Purpose",
        AlgorithmType.ZEROS: "Quick Wipe",
        AlgorithmType.CUSTOM: "User Defined"
    }
    return categories.get(algo_type, "Unknown")