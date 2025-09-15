"""
Wipe Verification Module

Provides verification capabilities to ensure data has been properly wiped.
Includes statistical analysis and entropy checking.
"""

import os
import time
import random
import logging
import hashlib
from typing import List, Tuple, Optional
from collections import Counter
import math

logger = logging.getLogger(__name__)


class WipeVerifier:
    """Handles verification of wipe operations."""

    def __init__(self, sample_size: int = 1024 * 1024):  # 1MB default sample size
        """
        Initialize wipe verifier.

        Args:
            sample_size: Size of random samples to read for verification
        """
        self.sample_size = sample_size

    def verify_wipe(self, device_path: str, device_size: int,
                   verification_type: str = "comprehensive") -> bool:
        """
        Verify that device has been properly wiped.

        Args:
            device_path: Path to device to verify
            device_size: Size of device in bytes
            verification_type: Type of verification (quick, comprehensive, paranoid)

        Returns:
            True if verification passed, False otherwise
        """
        logger.info(f"Starting {verification_type} verification of {device_path}")

        try:
            if verification_type == "quick":
                return self._quick_verification(device_path, device_size)
            elif verification_type == "comprehensive":
                return self._comprehensive_verification(device_path, device_size)
            elif verification_type == "paranoid":
                return self._paranoid_verification(device_path, device_size)
            else:
                raise ValueError(f"Unknown verification type: {verification_type}")

        except Exception as e:
            logger.error(f"Verification failed with error: {e}")
            return False

    def _quick_verification(self, device_path: str, device_size: int) -> bool:
        """
        Quick verification by checking a few random samples.

        Args:
            device_path: Path to device
            device_size: Device size in bytes

        Returns:
            True if quick verification passed
        """
        sample_count = min(10, device_size // self.sample_size)
        if sample_count == 0:
            sample_count = 1

        logger.debug(f"Quick verification with {sample_count} samples")

        with open(device_path, 'rb') as device:
            for _ in range(sample_count):
                # Read random sample
                position = random.randint(0, max(0, device_size - self.sample_size))
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                if self._contains_recoverable_data(data):
                    logger.warning(f"Potential data found at position {position}")
                    return False

        return True

    def _comprehensive_verification(self, device_path: str, device_size: int) -> bool:
        """
        Comprehensive verification with statistical analysis.

        Args:
            device_path: Path to device
            device_size: Device size in bytes

        Returns:
            True if comprehensive verification passed
        """
        sample_count = min(100, device_size // self.sample_size)
        if sample_count == 0:
            sample_count = 1

        logger.debug(f"Comprehensive verification with {sample_count} samples")

        entropy_scores = []
        pattern_detections = 0

        with open(device_path, 'rb') as device:
            for i in range(sample_count):
                # Read samples both randomly and sequentially
                if i % 2 == 0:
                    # Random position
                    position = random.randint(0, max(0, device_size - self.sample_size))
                else:
                    # Sequential position
                    position = (i // 2) * (device_size // (sample_count // 2))

                position = min(position, device_size - self.sample_size)
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                # Check for recoverable data patterns
                if self._contains_recoverable_data(data):
                    pattern_detections += 1

                # Calculate entropy
                entropy = self._calculate_entropy(data)
                entropy_scores.append(entropy)

        # Analyze results
        avg_entropy = sum(entropy_scores) / len(entropy_scores)
        pattern_percentage = (pattern_detections / sample_count) * 100

        logger.info(f"Verification results: avg_entropy={avg_entropy:.2f}, "
                   f"pattern_detections={pattern_percentage:.1f}%")

        # Thresholds for verification success
        if pattern_detections > sample_count * 0.05:  # More than 5% samples with patterns
            logger.warning(f"Too many data patterns detected: {pattern_percentage:.1f}%")
            return False

        if avg_entropy > 6.0:  # High entropy might indicate encrypted data remains
            logger.warning(f"High entropy detected: {avg_entropy:.2f}")
            return False

        return True

    def _paranoid_verification(self, device_path: str, device_size: int) -> bool:
        """
        Paranoid verification reading larger portions of the device.

        Args:
            device_path: Path to device
            device_size: Device size in bytes

        Returns:
            True if paranoid verification passed
        """
        # Read 1% of device or max 100MB, whichever is smaller
        read_size = min(device_size // 100, 100 * 1024 * 1024)
        if read_size < self.sample_size:
            read_size = min(self.sample_size, device_size)

        chunks = read_size // self.sample_size
        logger.debug(f"Paranoid verification reading {chunks} chunks totaling {read_size} bytes")

        pattern_detections = 0

        with open(device_path, 'rb') as device:
            for i in range(chunks):
                position = random.randint(0, max(0, device_size - self.sample_size))
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                if self._contains_recoverable_data(data):
                    pattern_detections += 1

                # Additional checks for specific data signatures
                if self._check_file_signatures(data):
                    logger.warning(f"File signature detected at position {position}")
                    return False

        pattern_percentage = (pattern_detections / chunks) * 100
        logger.info(f"Paranoid verification: {pattern_percentage:.1f}% patterns detected")

        return pattern_detections < chunks * 0.02  # Less than 2% pattern detection

    def _contains_recoverable_data(self, data: bytes) -> bool:
        """
        Check if data contains potentially recoverable information.

        Args:
            data: Data bytes to analyze

        Returns:
            True if recoverable data patterns are detected
        """
        if len(data) == 0:
            return False

        # Check for common text patterns
        if self._contains_text_patterns(data):
            return True

        # Check for structured data patterns
        if self._contains_structured_patterns(data):
            return True

        # Check entropy - very low entropy might indicate repeated patterns
        # that could contain recoverable data
        entropy = self._calculate_entropy(data)
        if entropy < 0.5:  # Very low entropy
            # Check if it's not just zeros or ones
            zero_count = data.count(0)
            ones_count = data.count(255)
            if zero_count / len(data) < 0.9 and ones_count / len(data) < 0.9:
                return True

        return False

    def _contains_text_patterns(self, data: bytes) -> bool:
        """Check for readable text patterns."""
        try:
            # Try to decode as common encodings
            text = data.decode('utf-8', errors='ignore')

            # Look for common words/patterns
            common_words = ['the', 'and', 'that', 'have', 'for', 'not', 'with', 'you']
            word_count = sum(1 for word in common_words if word in text.lower())

            if word_count > 2:
                return True

            # Look for email patterns
            if '@' in text and '.' in text:
                return True

            # Look for URL patterns
            if 'http' in text or 'www.' in text:
                return True

            # Look for file path patterns
            if text.count('/') > 3 or text.count('\\\\') > 3:
                return True

        except:
            pass

        return False

    def _contains_structured_patterns(self, data: bytes) -> bool:
        """Check for structured data patterns."""
        # Look for repeated patterns that might indicate data structures
        if len(data) < 16:
            return False

        # Check for NULL-terminated strings (common in C structures)
        null_positions = [i for i, b in enumerate(data) if b == 0]
        if len(null_positions) > len(data) // 20:  # More than 5% nulls might indicate structures
            # Check if nulls are in regular patterns
            if len(null_positions) > 1:
                gaps = [null_positions[i+1] - null_positions[i] for i in range(len(null_positions)-1)]
                if len(set(gaps)) <= 3:  # Regular gap patterns
                    return True

        # Look for repeating 4-byte or 8-byte patterns (common in binary structures)
        for pattern_size in [4, 8]:
            if len(data) >= pattern_size * 4:
                patterns = {}
                for i in range(0, len(data) - pattern_size, pattern_size):
                    pattern = data[i:i + pattern_size]
                    patterns[pattern] = patterns.get(pattern, 0) + 1

                # If we see the same pattern repeated many times
                max_repeats = max(patterns.values()) if patterns else 0
                if max_repeats > len(data) // (pattern_size * 10):
                    return True

        return False

    def _check_file_signatures(self, data: bytes) -> bool:
        """Check for known file format signatures."""
        if len(data) < 8:
            return False

        # Common file signatures
        signatures = [
            b'\\x89PNG',           # PNG
            b'\\xFF\\xD8\\xFF',    # JPEG
            b'GIF8',              # GIF
            b'%PDF',              # PDF
            b'PK\\x03\\x04',       # ZIP
            b'\\x50\\x4B\\x03\\x04', # ZIP (alternate)
            b'RIFF',              # WAV, AVI
            b'\\x1f\\x8b',         # GZIP
            b'BM',                # BMP
            b'\\x00\\x00\\x01\\x00', # ICO
            b'\\xFF\\xFB',         # MP3
            b'ID3',               # MP3
            b'Rar!',              # RAR
            b'7z\\xBC\\xAF\\x27\\x1C', # 7z
        ]

        for signature in signatures:
            if data.startswith(signature):
                return True

        return False

    def _calculate_entropy(self, data: bytes) -> float:
        """
        Calculate Shannon entropy of data.

        Args:
            data: Data to analyze

        Returns:
            Entropy value (0 to 8 for byte data)
        """
        if len(data) == 0:
            return 0

        # Count byte frequencies
        counts = Counter(data)

        # Calculate entropy
        entropy = 0
        for count in counts.values():
            probability = count / len(data)
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def generate_verification_report(self, device_path: str, verification_result: bool) -> dict:
        """
        Generate detailed verification report.

        Args:
            device_path: Path to verified device
            verification_result: Result of verification

        Returns:
            Dictionary containing verification report
        """
        return {
            'device_path': device_path,
            'verification_passed': verification_result,
            'verification_method': 'comprehensive',
            'timestamp': time.time(),
            'notes': 'Standard verification using entropy analysis and pattern detection'
        }