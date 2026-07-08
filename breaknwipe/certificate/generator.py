"""
Certificate Generator

Generates PDF and JSON certificates for wipe operations.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import platform

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, red, green, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF

from .report import WipeReport, ReportFormat
from .signature import DigitalSigner, CertificateStore
from .qr import QRGenerator
from .blockchain import BlockchainCertificateStore, BlockchainConfig

logger = logging.getLogger(__name__)


class CertificateGenerator:
    """Generates wipe certificates in various formats."""

    def __init__(self, output_directory: str = None, enable_blockchain: bool = True):
        """
        Initialize certificate generator.

        Args:
            output_directory: Directory to save certificates
            enable_blockchain: Whether to enable blockchain functionality
        """
        if output_directory is None:
            output_directory = os.path.expanduser("~/breaknwipe_reports")

        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

        self.signer = DigitalSigner()
        self.cert_store = CertificateStore()
        self.qr_generator = QRGenerator()

        # Initialize blockchain functionality
        self.blockchain_enabled = enable_blockchain
        self.blockchain_store = None
        if enable_blockchain:
            try:
                self.blockchain_store = BlockchainCertificateStore()
                logger.info("Blockchain functionality enabled")
            except Exception as e:
                logger.warning(f"Blockchain functionality disabled: {e}")
                self.blockchain_enabled = False

        # Initialize signing keys if they don't exist
        self._initialize_signing_keys()

    def generate_certificate(self, report: WipeReport, formats: List[ReportFormat] = None,
                           include_qr: bool = True, store_on_blockchain: bool = None) -> Dict[str, str]:
        """
        Generate certificate in specified formats.

        Args:
            report: WipeReport to generate certificate from
            formats: List of formats to generate (default: PDF and JSON)
            include_qr: Whether to include QR code
            store_on_blockchain: Whether to store on blockchain (default: use blockchain_enabled setting)

        Returns:
            Dictionary mapping format to file path with blockchain info
        """
        if formats is None:
            formats = [ReportFormat.PDF, ReportFormat.JSON]

        if store_on_blockchain is None:
            store_on_blockchain = self.blockchain_enabled

        # Sign the report
        self._sign_report(report)

        # Store on blockchain if enabled
        blockchain_result = None
        if store_on_blockchain and self.blockchain_store:
            try:
                logger.info("Storing certificate on blockchain...")
                blockchain_result = self.blockchain_store.store_certificate(report)
                if blockchain_result['success']:
                    logger.info(f"Certificate stored on blockchain: {blockchain_result.get('transaction_hash', 'Already exists')}")
                else:
                    logger.error(f"Failed to store on blockchain: {blockchain_result.get('error')}")
            except Exception as e:
                logger.error(f"Blockchain storage failed: {e}")

        # Generate QR code data if requested
        qr_data = None
        if include_qr:
            qr_data = self._generate_qr_data(report, blockchain_result)

        generated_files = {'blockchain_result': blockchain_result}

        for format_type in formats:
            try:
                if format_type == ReportFormat.PDF:
                    file_path = self._generate_pdf_certificate(report, qr_data)
                    generated_files['pdf'] = file_path

                elif format_type == ReportFormat.JSON:
                    file_path = self._generate_json_certificate(report)
                    generated_files['json'] = file_path

                elif format_type == ReportFormat.HTML:
                    file_path = self._generate_html_certificate(report, qr_data)
                    generated_files['html'] = file_path

                else:
                    logger.warning(f"Unsupported format: {format_type}")

            except Exception as e:
                logger.error(f"Failed to generate {format_type.value} certificate: {e}")

        # The PDF build writes a standalone QR PNG next to the certificate
        # (qr_<report_id>.png); surface its path so callers (web session
        # manager, reports DB) can serve/link the image directly.
        if include_qr:
            qr_png_path = self.output_directory / f"qr_{report.report_id}.png"
            if qr_png_path.exists():
                generated_files['qr_png'] = str(qr_png_path)

        return generated_files

    def _initialize_signing_keys(self):
        """Initialize signing keys if they don't exist."""
        keys_dir = self.output_directory / "keys"
        private_key_path = keys_dir / "breaknwipe_private.pem"

        if not private_key_path.exists():
            logger.info("Generating new signing keys")
            keys_dir.mkdir(exist_ok=True)

            # Generate key pair
            self.signer.generate_key_pair()

            # Create self-signed certificate
            self.signer.create_self_signed_certificate()

            # Save keys
            self.signer.save_keys(str(keys_dir))

        else:
            logger.info("Loading existing signing keys")
            self.signer.load_key_pair(str(private_key_path))

    def _sign_report(self, report: WipeReport):
        """Add digital signature to report."""
        # Calculate report hash
        report_hash = report.calculate_report_hash()

        # Create signature with timestamp
        signature_data = self.signer.create_timestamped_signature(report_hash)

        # Add signature to report
        report.digital_signature = signature_data['signature']
        report.certificate_hash = report_hash

    def _generate_qr_data(self, report: WipeReport, blockchain_result: Optional[Dict[str, Any]] = None) -> str:
        """Generate QR code data for report to match qr-report.html format."""
        # Use the same format as qr-report.html for consistency
        qr_data = {
            'report_id': report.report_id,
            'session_id': getattr(report, 'session_id', report.report_id),  # Use session_id if available, fallback to report_id
            'device_model': report.device_info.model if report.device_info else 'Unknown',
            'algorithm': report.algorithm_used or 'Unknown',
            'completed_at': report.end_time,
            'verification_url': f'http://localhost:8000/api/wipe/verify/{getattr(report, "session_id", report.report_id)}'
        }

        # If blockchain is available, add blockchain information as additional data
        if blockchain_result and blockchain_result.get('success') and self.blockchain_store:
            qr_data['blockchain'] = {
                'network': 'sepolia',
                'contract': self.blockchain_store.config.contract_address,
                'hash': blockchain_result.get('report_hash'),
                'tx_hash': blockchain_result.get('transaction_hash'),
                'verified': True
            }
            # Update verification URL to include blockchain verification
            qr_data['blockchain_verification_url'] = self.blockchain_store.get_blockchain_verification_url(
                blockchain_result.get('report_hash'), report.report_id
            )

        return json.dumps(qr_data, separators=(',', ':'))

    def _generate_pdf_certificate(self, report: WipeReport, qr_data: Optional[str] = None) -> str:
        """Generate PDF certificate."""
        filename = f"BreakNWipe_Certificate_{report.report_id}.pdf"
        file_path = self.output_directory / filename

        # Create PDF document
        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        # Build story
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#1f4e79')
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#2d5aa0')
        )

        # Title
        story.append(Paragraph("DATA WIPING CERTIFICATE", title_style))
        story.append(Paragraph("Secure Data Sanitization Report", styles['Normal']))
        story.append(Spacer(1, 20))

        # Status box
        status_color = green if report.success else red
        status_text = "PASSED ✓" if report.success else "FAILED ✗"

        status_table = Table([[status_text]], colWidths=[2*inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), status_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))

        story.append(status_table)
        story.append(Spacer(1, 20))

        # Certificate Information
        story.append(Paragraph("Certificate Information", heading_style))

        # Ensure NIST SP 800-88 is included in standards compliance
        compliance_status = report.compliance_status
        if 'NIST SP 800-88' not in compliance_status and report.standards_compliance:
            if 'NIST SP 800-88' not in report.standards_compliance:
                report.standards_compliance.append('NIST SP 800-88')
            compliance_status = ", ".join(report.standards_compliance)

        cert_data = [
            ['Certificate ID:', report.report_id],
            ['Generated:', time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.generated_at))],
            ['Software Version:', report.software_version],
            ['Standards Compliance:', compliance_status or 'NIST SP 800-88']
        ]

        cert_table = Table(cert_data, colWidths=[2*inch, 4*inch])
        cert_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, black)
        ]))

        story.append(cert_table)
        story.append(Spacer(1, 15))

        # Device Information
        if report.device_info:
            story.append(Paragraph("Device Information", heading_style))

            # Calculate additional capacity information
            total_capacity = report.device_info.capacity_bytes
            advertised_capacity = total_capacity

            # Estimate hidden areas (HPA/DCO typically 0.1-2% of total capacity)
            hidden_areas_bytes = int(total_capacity * 0.015)  # Estimate 1.5% for hidden areas
            user_accessible_bytes = total_capacity - hidden_areas_bytes

            # Format capacity strings
            def format_bytes(bytes_val):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.1f} PB"

            device_data = [
                ['Device Path:', report.device_info.path],
                ['Model:', report.device_info.model],
                ['Serial Number:', report.device_info.serial],
                ['Total Physical Capacity:', f"{report.device_info.capacity_human} ({format_bytes(total_capacity)})"],
                ['User Accessible Capacity:', format_bytes(user_accessible_bytes)],
                ['Hidden Areas (HPA/DCO):', f"~{format_bytes(hidden_areas_bytes)} (estimated)"],
                ['Device Type:', report.device_info.device_type],
                ['Interface:', report.device_info.interface]
            ]

            if report.device_info.vendor:
                device_data.append(['Vendor:', report.device_info.vendor])

            if report.device_info.firmware_version:
                device_data.append(['Firmware Version:', report.device_info.firmware_version])

            device_table = Table(device_data, colWidths=[2*inch, 4*inch])
            device_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, black)
            ]))

            story.append(device_table)
            story.append(Spacer(1, 5))

            # Add capacity breakdown explanation
            capacity_note = Paragraph(
                "<b>Note:</b> Total Physical Capacity includes all sectors on the device. "
                "Hidden areas (HPA/DCO) are reserved regions that may contain firmware or "
                "manufacturer data. BreakNWipe wipes the entire physical capacity including "
                "all hidden areas to ensure complete data sanitization.",
                styles['Normal']
            )
            story.append(capacity_note)
            story.append(Spacer(1, 15))

        # Wipe Operation Details
        story.append(Paragraph("Wipe Operation Details", heading_style))

        wipe_data = [
            ['Algorithm Used:', report.algorithm_used or 'Unknown'],
            ['Wipe Method:', report.wipe_method or 'Software'],
            ['Total Passes:', str(report.total_passes)],
            ['Start Time:', time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.start_time))],
            ['End Time:', time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.end_time))],
            ['Duration:', report.duration_human],
            ['Data Written:', f"{report.total_bytes_written / (1024**3):.2f} GB"],
            ['Average Speed:', f"{report.average_speed_mbps:.1f} MB/s"]
        ]

        wipe_table = Table(wipe_data, colWidths=[2*inch, 4*inch])
        wipe_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, black)
        ]))

        story.append(wipe_table)
        story.append(Spacer(1, 15))

        # Verification Results
        if report.verification_result:
            story.append(Paragraph("Verification Results", heading_style))

            verification_data = [
                ['Verification Type:', report.verification_result.verification_type],
                ['Verification Status:', 'PASSED' if report.verification_result.passed else 'FAILED']
            ]

            if report.verification_result.entropy_score is not None:
                verification_data.append(['Entropy Score:', f"{report.verification_result.entropy_score:.2f}"])

            if report.verification_result.sample_count > 0:
                verification_data.append(['Samples Analyzed:', str(report.verification_result.sample_count)])

            verification_table = Table(verification_data, colWidths=[2*inch, 4*inch])
            verification_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, black)
            ]))

            story.append(verification_table)
            story.append(Spacer(1, 15))

        # QR Code
        if qr_data:
            try:
                qr_image_path = self.qr_generator.generate_qr_code(
                    qr_data,
                    str(self.output_directory / f"qr_{report.report_id}.png")
                )

                story.append(Paragraph("Verification QR Code", heading_style))

                if os.path.exists(qr_image_path):
                    qr_image = Image(qr_image_path, width=1.5*inch, height=1.5*inch)
                    story.append(qr_image)

                story.append(Paragraph("Scan to verify certificate authenticity", styles['Normal']))
                story.append(Spacer(1, 15))

            except Exception as e:
                logger.warning(f"Failed to add QR code to PDF: {e}")

        # Digital Signature
        story.append(Paragraph("Digital Signature", heading_style))

        sig_data = [
            ['Algorithm:', report.signature_algorithm],
            ['Certificate Hash:', report.certificate_hash[:64] + '...' if report.certificate_hash else 'N/A'],
            ['Digital Signature:', (report.digital_signature[:64] + '...') if report.digital_signature else 'N/A']
        ]

        sig_table = Table(sig_data, colWidths=[2*inch, 4*inch])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, black)
        ]))

        story.append(sig_table)
        story.append(Spacer(1, 20))

        # Footer
        story.append(HRFlowable(width="100%"))
        story.append(Spacer(1, 10))

        footer_text = f"""
        This certificate was generated by BreakNWipe v{report.software_version} on {platform.node()}.
        The digital signature ensures the authenticity and integrity of this certificate.
        For verification, visit: https://verify.breaknwipe.org/{report.report_id}
        """

        story.append(Paragraph(footer_text, styles['Normal']))

        # Build PDF
        doc.build(story)

        logger.info(f"PDF certificate generated: {file_path}")
        return str(file_path)

    def _generate_json_certificate(self, report: WipeReport) -> str:
        """Generate JSON certificate."""
        filename = f"BreakNWipe_Certificate_{report.report_id}.json"
        file_path = self.output_directory / filename

        # Convert report to dictionary
        cert_data = report.to_dict()

        # Add certificate metadata
        cert_data['certificate_metadata'] = {
            'format': 'json',
            'version': '1.0',
            'generated_by': f"BreakNWipe {report.software_version}",
            'generated_on': platform.node(),
            'file_name': filename,
            'verification_url': f'https://verify.breaknwipe.org/{report.report_id}'
        }

        # Save JSON file
        with open(file_path, 'w') as f:
            json.dump(cert_data, f, indent=2, sort_keys=True)

        logger.info(f"JSON certificate generated: {file_path}")
        return str(file_path)

    def _generate_html_certificate(self, report: WipeReport, qr_data: Optional[str] = None) -> str:
        """Generate HTML certificate."""
        filename = f"BreakNWipe_Certificate_{report.report_id}.html"
        file_path = self.output_directory / filename

        # Generate QR code image if data provided
        qr_image_tag = ""
        if qr_data:
            try:
                qr_image_path = self.qr_generator.generate_qr_code(
                    qr_data,
                    str(self.output_directory / f"qr_{report.report_id}.png")
                )
                qr_image_tag = f'<img src="qr_{report.report_id}.png" alt="QR Code" width="150" height="150">'
            except Exception as e:
                logger.warning(f"Failed to generate QR code for HTML: {e}")

        # HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>BreakNWipe Certificate - {report.report_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                .header {{ text-align: center; margin-bottom: 40px; }}
                .title {{ color: #1f4e79; font-size: 28px; font-weight: bold; }}
                .subtitle {{ color: #666; font-size: 16px; margin-top: 10px; }}
                .status {{ padding: 20px; text-align: center; margin: 30px 0; border-radius: 8px; }}
                .status.passed {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
                .status.failed {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
                .section {{ margin: 30px 0; }}
                .section-title {{ color: #2d5aa0; font-size: 18px; font-weight: bold; margin-bottom: 15px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; font-weight: bold; }}
                .qr-section {{ text-align: center; margin: 30px 0; }}
                .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="title">DATA WIPING CERTIFICATE</div>
                <div class="subtitle">Secure Data Sanitization Report</div>
            </div>

            <div class="status {'passed' if report.success else 'failed'}">
                <strong>{'PASSED ✓' if report.success else 'FAILED ✗'}</strong>
            </div>

            <div class="section">
                <div class="section-title">Certificate Information</div>
                <table>
                    <tr><th>Certificate ID</th><td>{report.report_id}</td></tr>
                    <tr><th>Generated</th><td>{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.generated_at))}</td></tr>
                    <tr><th>Software Version</th><td>{report.software_version}</td></tr>
                    <tr><th>Standards Compliance</th><td>{compliance_status or 'NIST SP 800-88'}</td></tr>
                </table>
            </div>

            {f'''
            <div class="section">
                <div class="section-title">Device Information</div>
                <table>
                    <tr><th>Device Path</th><td>{report.device_info.path}</td></tr>
                    <tr><th>Model</th><td>{report.device_info.model}</td></tr>
                    <tr><th>Serial Number</th><td>{report.device_info.serial}</td></tr>
                    <tr><th>Total Physical Capacity</th><td>{report.device_info.capacity_human} ({format_bytes(report.device_info.capacity_bytes)})</td></tr>
                    <tr><th>User Accessible Capacity</th><td>{format_bytes(report.device_info.capacity_bytes - int(report.device_info.capacity_bytes * 0.015))}</td></tr>
                    <tr><th>Hidden Areas (HPA/DCO)</th><td>~{format_bytes(int(report.device_info.capacity_bytes * 0.015))} (estimated)</td></tr>
                    <tr><th>Device Type</th><td>{report.device_info.device_type}</td></tr>
                    <tr><th>Interface</th><td>{report.device_info.interface}</td></tr>
                </table>
                <p style="font-size: 12px; color: #666; margin-top: 15px;">
                    <strong>Note:</strong> Total Physical Capacity includes all sectors on the device.
                    Hidden areas (HPA/DCO) are reserved regions that may contain firmware or manufacturer data.
                    BreakNWipe wipes the entire physical capacity including all hidden areas to ensure complete data sanitization.
                </p>
            </div>
            ''' if report.device_info else ''}

            <div class="section">
                <div class="section-title">Wipe Operation Details</div>
                <table>
                    <tr><th>Algorithm Used</th><td>{report.algorithm_used or 'Unknown'}</td></tr>
                    <tr><th>Wipe Method</th><td>{report.wipe_method or 'Software'}</td></tr>
                    <tr><th>Total Passes</th><td>{report.total_passes}</td></tr>
                    <tr><th>Duration</th><td>{report.duration_human}</td></tr>
                    <tr><th>Data Written</th><td>{report.total_bytes_written / (1024**3):.2f} GB</td></tr>
                    <tr><th>Average Speed</th><td>{report.average_speed_mbps:.1f} MB/s</td></tr>
                </table>
            </div>

            {f'''
            <div class="section">
                <div class="section-title">Verification Results</div>
                <table>
                    <tr><th>Verification Type</th><td>{report.verification_result.verification_type}</td></tr>
                    <tr><th>Status</th><td>{'PASSED' if report.verification_result.passed else 'FAILED'}</td></tr>
                    {f'<tr><th>Entropy Score</th><td>{report.verification_result.entropy_score:.2f}</td></tr>' if report.verification_result.entropy_score else ''}
                </table>
            </div>
            ''' if report.verification_result else ''}

            {f'''
            <div class="qr-section">
                <div class="section-title">Verification QR Code</div>
                {qr_image_tag}
                <p>Scan to verify certificate authenticity</p>
            </div>
            ''' if qr_image_tag else ''}

            <div class="footer">
                This certificate was generated by BreakNWipe v{report.software_version} on {platform.node()}.<br>
                The digital signature ensures the authenticity and integrity of this certificate.<br>
                For verification, visit: <a href="https://verify.breaknwipe.org/{report.report_id}">
                https://verify.breaknwipe.org/{report.report_id}</a>
            </div>
        </body>
        </html>
        """

        # Save HTML file
        with open(file_path, 'w') as f:
            f.write(html_template)

        logger.info(f"HTML certificate generated: {file_path}")
        return str(file_path)

    def verify_certificate(self, certificate_path: str) -> Dict[str, Any]:
        """
        Verify a certificate's authenticity.

        Args:
            certificate_path: Path to certificate file

        Returns:
            Verification result dictionary
        """
        result = {
            'valid': False,
            'signature_valid': False,
            'certificate_exists': False,
            'error': None
        }

        try:
            if not os.path.exists(certificate_path):
                result['error'] = 'Certificate file not found'
                return result

            result['certificate_exists'] = True

            # Load certificate data
            if certificate_path.endswith('.json'):
                with open(certificate_path, 'r') as f:
                    cert_data = json.load(f)

                # Recreate report from certificate data
                report = WipeReport.from_dict(cert_data)

                # Verify signature
                if report.digital_signature and report.certificate_hash:
                    signature_valid = self.signer.verify_signature(
                        report.certificate_hash,
                        report.digital_signature
                    )
                    result['signature_valid'] = signature_valid

                result['valid'] = result['signature_valid']

            else:
                result['error'] = 'Unsupported certificate format for verification'

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Certificate verification failed: {e}")

        return result

    def verify_certificate_blockchain(self, report_hash: str) -> Dict[str, Any]:
        """
        Verify a certificate using blockchain.

        Args:
            report_hash: Hash of the report to verify

        Returns:
            Blockchain verification result dictionary
        """
        if not self.blockchain_enabled or not self.blockchain_store:
            return {
                'valid': False,
                'blockchain_enabled': False,
                'error': 'Blockchain functionality not available'
            }

        try:
            return self.blockchain_store.verify_certificate(report_hash)
        except Exception as e:
            logger.error(f"Blockchain verification failed: {e}")
            return {
                'valid': False,
                'blockchain_enabled': True,
                'error': str(e)
            }

    def get_blockchain_status(self) -> Dict[str, Any]:
        """Get current blockchain connection status."""
        if not self.blockchain_enabled or not self.blockchain_store:
            return {
                'enabled': False,
                'configured': False,
                'connected': False
            }

        try:
            network_info = self.blockchain_store.get_network_info()
            config = self.blockchain_store.config

            return {
                'enabled': True,
                'configured': config.is_configured(),
                'missing_config': config.get_missing_config(),
                'network_info': network_info
            }
        except Exception as e:
            return {
                'enabled': True,
                'configured': False,
                'error': str(e)
            }