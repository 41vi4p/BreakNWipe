"""
QR Code Generator

Generates QR codes for certificate verification and terminal display.
"""

import os
import json
import logging
from typing import Optional, Dict, Any

import qrcode
from qrcode.console_scripts import main as qr_terminal
import io
import sys

logger = logging.getLogger(__name__)


class QRGenerator:
    """Generates QR codes for certificates and verification."""

    def __init__(self):
        """Initialize QR generator."""
        pass

    def generate_qr_code(self, data: str, output_path: Optional[str] = None,
                        size: int = 10, border: int = 4) -> str:
        """
        Generate QR code image file.

        Args:
            data: Data to encode in QR code
            output_path: Path to save QR code image (optional)
            size: QR code size (default 10)
            border: Border size (default 4)

        Returns:
            Path to generated QR code image
        """
        try:
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,  # Controls size, 1 is smallest
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=border,
            )

            # Add data
            qr.add_data(data)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Save to file
            if output_path:
                img.save(output_path)
                logger.info(f"QR code saved to: {output_path}")
                return output_path
            else:
                # Generate temporary filename
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                img.save(temp_file.name)
                temp_file.close()
                logger.info(f"QR code saved to temporary file: {temp_file.name}")
                return temp_file.name

        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            raise

    def generate_terminal_qr(self, data: str, invert: bool = False) -> str:
        """
        Generate QR code for terminal display.

        Args:
            data: Data to encode in QR code
            invert: Whether to invert colors (default False)

        Returns:
            String representation of QR code for terminal
        """
        try:
            # Create QR code instance optimized for terminal
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=2,
            )

            # Add data
            qr.add_data(data)
            qr.make(fit=True)

            # Get terminal-friendly output
            output = io.StringIO()
            qr.print_ascii(out=output, invert=invert)
            terminal_qr = output.getvalue()
            output.close()

            return terminal_qr

        except Exception as e:
            logger.error(f"Failed to generate terminal QR code: {e}")
            raise

    def display_terminal_qr(self, data: str, title: Optional[str] = None):
        """
        Display QR code in terminal.

        Args:
            data: Data to encode in QR code
            title: Optional title to display above QR code
        """
        try:
            if title:
                print(f"\n{title}")
                print("=" * len(title))

            terminal_qr = self.generate_terminal_qr(data)
            print(terminal_qr)

            # Add some helpful text
            print("Scan this QR code to verify the certificate or access the report.")
            print(f"Data: {data[:100]}{'...' if len(data) > 100 else ''}")

        except Exception as e:
            logger.error(f"Failed to display terminal QR code: {e}")
            print(f"Error generating QR code: {e}")

    def create_verification_qr_data(self, report_id: str, report_hash: str,
                                  additional_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Create QR code data for certificate verification.

        Args:
            report_id: Report ID
            report_hash: Report hash for verification
            additional_data: Additional data to include

        Returns:
            JSON string for QR code
        """
        qr_data = {
            'type': 'breaknwipe_certificate',
            'report_id': report_id,
            'hash': report_hash,
            'verify_url': f'https://verify.breaknwipe.org/{report_id}',
            'version': '1.0'
        }

        if additional_data:
            qr_data.update(additional_data)

        return json.dumps(qr_data, separators=(',', ':'))

    def create_device_info_qr_data(self, device_path: str, device_serial: str,
                                 wipe_success: bool, algorithm: str) -> str:
        """
        Create QR code data for device information.

        Args:
            device_path: Device path
            device_serial: Device serial number
            wipe_success: Whether wipe was successful
            algorithm: Algorithm used

        Returns:
            JSON string for QR code
        """
        qr_data = {
            'type': 'device_wipe_result',
            'device': device_path,
            'serial': device_serial,
            'status': 'PASSED' if wipe_success else 'FAILED',
            'algorithm': algorithm,
            'timestamp': int(time.time()),
            'version': '1.0'
        }

        return json.dumps(qr_data, separators=(',', ':'))

    def parse_qr_data(self, qr_data: str) -> Optional[Dict[str, Any]]:
        """
        Parse QR code data.

        Args:
            qr_data: QR code data string

        Returns:
            Parsed data dictionary or None if invalid
        """
        try:
            data = json.loads(qr_data)

            # Validate basic structure
            if not isinstance(data, dict):
                return None

            if 'type' not in data:
                return None

            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse QR data: {e}")
            return None

    def generate_compact_qr(self, essential_data: Dict[str, Any]) -> str:
        """
        Generate compact QR code data with only essential information.

        Args:
            essential_data: Essential data to encode

        Returns:
            Compact data string for QR code
        """
        # Create compact representation
        compact_parts = []

        # Add type identifier
        compact_parts.append(essential_data.get('type', 'unknown')[:3])

        # Add report ID (first 8 characters)
        if 'report_id' in essential_data:
            compact_parts.append(essential_data['report_id'][:8])

        # Add status
        if 'status' in essential_data:
            compact_parts.append('P' if essential_data['status'] == 'PASSED' else 'F')

        # Add hash (first 16 characters)
        if 'hash' in essential_data:
            compact_parts.append(essential_data['hash'][:16])

        return '|'.join(compact_parts)

    def create_multi_format_qr(self, data: str, base_filename: str) -> Dict[str, str]:
        """
        Create QR codes in multiple formats.

        Args:
            data: Data to encode
            base_filename: Base filename (without extension)

        Returns:
            Dictionary mapping format to file path
        """
        formats = {}

        try:
            # PNG format
            png_path = f"{base_filename}.png"
            formats['png'] = self.generate_qr_code(data, png_path)

            # SVG format
            try:
                import qrcode.image.svg
                factory = qrcode.image.svg.SvgPathImage

                qr = qrcode.QRCode(image_factory=factory)
                qr.add_data(data)
                qr.make()

                svg_path = f"{base_filename}.svg"
                img = qr.make_image()
                img.save(svg_path)
                formats['svg'] = svg_path

            except ImportError:
                logger.debug("SVG support not available")

            # Terminal format
            terminal_path = f"{base_filename}.txt"
            terminal_qr = self.generate_terminal_qr(data)

            with open(terminal_path, 'w') as f:
                f.write(terminal_qr)

            formats['terminal'] = terminal_path

        except Exception as e:
            logger.error(f"Failed to create multi-format QR codes: {e}")

        return formats

    def validate_qr_size(self, data: str) -> Dict[str, Any]:
        """
        Validate QR code data size and suggest optimizations.

        Args:
            data: Data to encode

        Returns:
            Validation result with size info and suggestions
        """
        result = {
            'data_length': len(data),
            'estimated_qr_size': None,
            'recommended': True,
            'suggestions': []
        }

        # QR code capacity limits (approximate)
        capacity_limits = {
            'L': 2953,  # Low error correction
            'M': 2331,  # Medium error correction
            'Q': 1663,  # Quartile error correction
            'H': 1273   # High error correction
        }

        data_length = len(data)

        if data_length > capacity_limits['L']:
            result['recommended'] = False
            result['suggestions'].append('Data too large for QR code')

        elif data_length > capacity_limits['M']:
            result['suggestions'].append('Consider using low error correction')

        elif data_length > capacity_limits['Q']:
            result['suggestions'].append('Consider compacting data or using medium error correction')

        # Estimate QR version needed
        if data_length <= 25:
            result['estimated_qr_size'] = 'Small (21x21)'
        elif data_length <= 47:
            result['estimated_qr_size'] = 'Medium (25x25)'
        elif data_length <= 77:
            result['estimated_qr_size'] = 'Large (29x29)'
        else:
            result['estimated_qr_size'] = 'Very Large (33x33+)'

        return result

    def create_animated_qr_sequence(self, data_chunks: list, output_dir: str) -> list:
        """
        Create sequence of QR codes for large data (animated QR).

        Args:
            data_chunks: List of data chunks to encode
            output_dir: Directory to save QR sequence

        Returns:
            List of file paths for QR sequence
        """
        os.makedirs(output_dir, exist_ok=True)
        sequence_files = []

        for i, chunk in enumerate(data_chunks):
            # Add sequence metadata
            chunk_data = {
                'part': i + 1,
                'total': len(data_chunks),
                'data': chunk
            }

            chunk_json = json.dumps(chunk_data, separators=(',', ':'))

            # Generate QR code for this chunk
            qr_path = os.path.join(output_dir, f"qr_part_{i+1:02d}.png")
            self.generate_qr_code(chunk_json, qr_path)
            sequence_files.append(qr_path)

        logger.info(f"Generated {len(sequence_files)} QR codes for animated sequence")
        return sequence_files