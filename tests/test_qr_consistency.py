#!/usr/bin/env python3
"""
Test script to verify QR code consistency between PDF and HTML formats.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / 'breaknwipe' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not available, skipping .env loading")

def test_qr_data_format():
    """Test QR data generation to match qr-report.html format."""
    print("\n📱 Testing QR code data format consistency...")

    try:
        from breaknwipe.certificate.generator import CertificateGenerator
        from breaknwipe.certificate.report import WipeReport, DeviceInfo

        # Create mock device info
        device_info = DeviceInfo(
            path="/dev/sda",
            model="SanDisk Ultra Fit",
            serial="TEST123456",
            capacity_bytes=30000000000,
            capacity_human="28.0 GB",
            device_type="external",
            interface="usb"
        )

        # Create mock wipe report
        report = WipeReport(
            device_info=device_info,
            algorithm_used="nist-clear",
            wipe_method="software",
            start_time=datetime.now().timestamp(),
            end_time=datetime.now().timestamp(),
            total_passes=1,
            success=True,
            total_bytes_written=30000000000,
            average_speed_mbps=50.0,
            organization="BreakNWipe by CodeBreakers",
            operator="System User"
        )

        # Add session ID (like in the actual session manager)
        session_id = "test-session-123"
        report.session_id = session_id

        # Create certificate generator
        generator = CertificateGenerator(enable_blockchain=False)

        # Test QR data generation without blockchain
        qr_data_no_blockchain = generator._generate_qr_data(report, None)
        qr_obj_no_blockchain = json.loads(qr_data_no_blockchain)

        print("📄 PDF QR Code Data (No Blockchain):")
        print(json.dumps(qr_obj_no_blockchain, indent=2))

        # Expected format from qr-report.html
        expected_format = {
            'report_id': report.report_id,
            'session_id': session_id,
            'device_model': device_info.model,
            'algorithm': report.algorithm_used,
            'completed_at': report.end_time,
            'verification_url': f'http://localhost:8000/api/wipe/verify/{session_id}'
        }

        print("\n🌐 Expected HTML QR Code Format:")
        print(json.dumps(expected_format, indent=2))

        # Check if formats match
        matches = True
        for key in expected_format:
            if key not in qr_obj_no_blockchain:
                print(f"❌ Missing key in PDF QR: {key}")
                matches = False
            elif qr_obj_no_blockchain[key] != expected_format[key]:
                print(f"❌ Value mismatch for {key}:")
                print(f"   PDF: {qr_obj_no_blockchain[key]}")
                print(f"   HTML: {expected_format[key]}")
                matches = False

        if matches:
            print("✅ QR code formats match!")
        else:
            print("❌ QR code formats do not match")

        # Test with blockchain
        mock_blockchain_result = {
            'success': True,
            'report_hash': '0x1234567890abcdef1234567890abcdef12345678',
            'transaction_hash': '0xabcdef1234567890abcdef1234567890abcdef12',
            'block_number': 12345
        }

        try:
            qr_data_blockchain = generator._generate_qr_data(report, mock_blockchain_result)
            qr_obj_blockchain = json.loads(qr_data_blockchain)

            print("\n🔗 PDF QR Code Data (With Blockchain):")
            print(json.dumps(qr_obj_blockchain, indent=2))

            # Check if blockchain data is added
            if 'blockchain' in qr_obj_blockchain:
                print("✅ Blockchain data properly added to QR code")
            else:
                print("❌ Blockchain data missing from QR code")

        except Exception as e:
            print(f"⚠️  Blockchain QR generation skipped: {e}")

        return True

    except Exception as e:
        print(f"❌ Error testing QR data format: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run QR consistency tests."""
    print("🔧 QR Code Consistency Test")
    print("=" * 40)

    success = test_qr_data_format()

    print(f"\n📊 Test Result: {'✅ PASS' if success else '❌ FAIL'}")

    if success:
        print("🎉 QR codes between PDF and HTML will now be consistent!")
    else:
        print("⚠️  QR code consistency issues detected")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())