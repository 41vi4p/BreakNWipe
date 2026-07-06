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
        try:
            return self.verify_wipe_detailed(device_path, device_size, verification_type)['passed']
        except Exception as e:
            logger.error(f"Verification failed with error: {e}")
            return False

    def verify_wipe_detailed(self, device_path: str, device_size: int,
                             verification_type: str = "comprehensive") -> dict:
        """
        Verify that a device has been properly wiped, returning the full
        statistics behind the pass/fail verdict (sample count, entropy,
        pattern-detection rate, and any file-signature hits with their byte
        offsets) -- used by the GUI/CLI "Verify erasure" feature so the result
        is explainable, not just a bare boolean.
        """
        logger.info(f"Starting {verification_type} verification of {device_path}")

        if verification_type == "quick":
            return self._quick_verification(device_path, device_size)
        elif verification_type == "comprehensive":
            return self._comprehensive_verification(device_path, device_size)
        elif verification_type == "paranoid":
            return self._paranoid_verification(device_path, device_size)
        else:
            raise ValueError(f"Unknown verification type: {verification_type}")

    def _quick_verification(self, device_path: str, device_size: int) -> dict:
        """Quick verification by checking a few random samples."""
        sample_count = min(10, device_size // self.sample_size)
        if sample_count == 0:
            sample_count = 1

        logger.debug(f"Quick verification with {sample_count} samples")

        pattern_detections = 0
        entropy_scores = []
        signature_hits = []

        with open(device_path, 'rb') as device:
            for _ in range(sample_count):
                position = random.randint(0, max(0, device_size - self.sample_size))
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                entropy_scores.append(self._calculate_entropy(data))
                if self._contains_recoverable_data(data):
                    pattern_detections += 1
                    logger.warning(f"Potential data found at position {position}")
                sig = self._check_file_signatures(data)
                if sig:
                    signature_hits.append({'offset': position, 'signature': sig})

        passed = pattern_detections == 0 and not signature_hits
        return {
            'passed': passed,
            'verification_type': 'quick',
            'samples_checked': sample_count,
            'avg_entropy': sum(entropy_scores) / len(entropy_scores) if entropy_scores else 0.0,
            'pattern_detections': pattern_detections,
            'pattern_detection_percent': (pattern_detections / sample_count) * 100,
            'signature_hits': signature_hits,
            'notes': [] if passed else ['Recoverable-looking data or file signatures were found in sampled sectors.'],
        }

    def _comprehensive_verification(self, device_path: str, device_size: int) -> dict:
        """Comprehensive verification with statistical analysis."""
        sample_count = min(100, device_size // self.sample_size)
        if sample_count == 0:
            sample_count = 1

        logger.debug(f"Comprehensive verification with {sample_count} samples")

        entropy_scores = []
        pattern_detections = 0
        signature_hits = []

        with open(device_path, 'rb') as device:
            for i in range(sample_count):
                # Read samples both randomly and sequentially
                if i % 2 == 0:
                    position = random.randint(0, max(0, device_size - self.sample_size))
                else:
                    position = (i // 2) * (device_size // (sample_count // 2))

                position = min(position, device_size - self.sample_size)
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                if self._contains_recoverable_data(data):
                    pattern_detections += 1

                sig = self._check_file_signatures(data)
                if sig:
                    signature_hits.append({'offset': position, 'signature': sig})

                entropy_scores.append(self._calculate_entropy(data))

        avg_entropy = sum(entropy_scores) / len(entropy_scores)
        pattern_percentage = (pattern_detections / sample_count) * 100

        logger.info(f"Verification results: avg_entropy={avg_entropy:.2f}, "
                   f"pattern_detections={pattern_percentage:.1f}%")

        notes = []
        passed = True
        if pattern_detections > sample_count * 0.05:  # More than 5% samples with patterns
            passed = False
            notes.append(f"Data-like patterns detected in {pattern_percentage:.1f}% of sampled sectors.")
        if signature_hits:
            passed = False
            notes.append(f"{len(signature_hits)} known file signature(s) found in sampled sectors.")
        if avg_entropy > 6.0:
            # High entropy alone isn't damning -- crypto-erase and random-fill
            # wipes are *supposed* to leave high-entropy data -- but it can
            # also mean genuine file content remains, so it's surfaced as a
            # note rather than an automatic fail.
            notes.append(f"High average entropy ({avg_entropy:.2f}/8) -- expected after a random-fill or "
                         f"crypto-erase wipe, but also consistent with un-overwritten file data.")

        return {
            'passed': passed,
            'verification_type': 'comprehensive',
            'samples_checked': sample_count,
            'avg_entropy': avg_entropy,
            'pattern_detections': pattern_detections,
            'pattern_detection_percent': pattern_percentage,
            'signature_hits': signature_hits,
            'notes': notes,
        }

    def _paranoid_verification(self, device_path: str, device_size: int) -> dict:
        """Paranoid verification reading larger portions of the device."""
        # Read 1% of device or max 100MB, whichever is smaller
        read_size = min(device_size // 100, 100 * 1024 * 1024)
        if read_size < self.sample_size:
            read_size = min(self.sample_size, device_size)

        chunks = read_size // self.sample_size
        if chunks == 0:
            chunks = 1
        logger.debug(f"Paranoid verification reading {chunks} chunks totaling {read_size} bytes")

        pattern_detections = 0
        entropy_scores = []
        signature_hits = []

        with open(device_path, 'rb') as device:
            for _ in range(chunks):
                position = random.randint(0, max(0, device_size - self.sample_size))
                device.seek(position)
                data = device.read(min(self.sample_size, device_size - position))

                entropy_scores.append(self._calculate_entropy(data))
                if self._contains_recoverable_data(data):
                    pattern_detections += 1

                sig = self._check_file_signatures(data)
                if sig:
                    signature_hits.append({'offset': position, 'signature': sig})
                    logger.warning(f"File signature detected at position {position}")

        pattern_percentage = (pattern_detections / chunks) * 100
        logger.info(f"Paranoid verification: {pattern_percentage:.1f}% patterns detected")

        passed = pattern_detections < chunks * 0.02 and not signature_hits  # Less than 2% pattern detection
        notes = []
        if not passed:
            if signature_hits:
                notes.append(f"{len(signature_hits)} known file signature(s) found in sampled sectors.")
            if pattern_detections >= chunks * 0.02:
                notes.append(f"Data-like patterns detected in {pattern_percentage:.1f}% of sampled sectors.")

        return {
            'passed': passed,
            'verification_type': 'paranoid',
            'samples_checked': chunks,
            'avg_entropy': sum(entropy_scores) / len(entropy_scores) if entropy_scores else 0.0,
            'pattern_detections': pattern_detections,
            'pattern_detection_percent': pattern_percentage,
            'signature_hits': signature_hits,
            'notes': notes,
        }

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

    def _check_file_signatures(self, data: bytes) -> Optional[str]:
        """
        Look for known file-format magic bytes anywhere in a sample. Returns
        the matched format's name, or None.

        Note: these must be real byte literals (`b'\\x89PNG'` in Python source
        is the *escaped* form that decodes to `\x89PNG` at runtime -- not to be
        confused with the doubled-backslash string `b'\\\\x89PNG'`, which is 7
        literal ASCII characters and would never match real binary data. An
        earlier version of this file used the doubled form, silently disabling
        every binary signature check.
        """
        if len(data) < 8:
            return None

        signatures = [
            (b'\x89PNG', 'PNG'),
            (b'\xff\xd8\xff', 'JPEG'),
            (b'GIF8', 'GIF'),
            (b'%PDF', 'PDF'),
            (b'PK\x03\x04', 'ZIP'),
            (b'RIFF', 'RIFF (WAV/AVI)'),
            (b'\x1f\x8b', 'GZIP'),
            (b'BM', 'BMP'),
            (b'\x00\x00\x01\x00', 'ICO'),
            (b'ID3', 'MP3 (ID3)'),
            (b'Rar!', 'RAR'),
            (b'7z\xbc\xaf\x27\x1c', '7-Zip'),
        ]

        for signature, name in signatures:
            if signature in data:
                return name

        return None

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