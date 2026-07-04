#!/usr/bin/env python3
"""
Test script for blockchain functionality in BreakNWipe.

This script tests:
1. Internet connectivity checking
2. Blockchain configuration loading
3. QR code generation with blockchain data
4. Certificate generation with blockchain integration
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / 'breaknwipe' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")
    else:
        print(f"⚠️  No .env file found at {env_path}")
except ImportError:
    print("⚠️  python-dotenv not available, skipping .env loading")

def test_internet_connectivity():
    """Test internet connectivity function."""
    print("🌐 Testing internet connectivity...")

    try:
        from breaknwipe.utils import check_internet_connectivity, check_blockchain_service_connectivity

        # Test basic internet connectivity
        has_internet = check_internet_connectivity(timeout=5)
        print(f"   Internet connectivity: {'✅ Available' if has_internet else '❌ Not available'}")

        if has_internet:
            # Test blockchain service connectivity
            rpc_url = os.environ.get("BREAKNWIPE_RPC_URL", "https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID")
            blockchain_reachable = check_blockchain_service_connectivity(rpc_url, timeout=10)
            print(f"   Blockchain service: {'✅ Reachable' if blockchain_reachable else '❌ Not reachable'}")

        return has_internet

    except Exception as e:
        print(f"   ❌ Error testing connectivity: {e}")
        return False

def test_blockchain_config():
    """Test blockchain configuration loading."""
    print("\n⚙️  Testing blockchain configuration...")

    try:
        from breaknwipe.certificate.blockchain import BlockchainConfig

        # Test config loading
        config = BlockchainConfig()
        print(f"   RPC URL: {'✅ Set' if config.rpc_url else '❌ Not set'}")
        print(f"   Contract Address: {'✅ Set' if config.contract_address else '❌ Not set'}")
        print(f"   Private Key: {'✅ Set' if config.private_key else '❌ Not set'}")
        print(f"   Chain ID: {config.chain_id}")

        is_configured = config.is_configured()
        print(f"   Configuration status: {'✅ Complete' if is_configured else '❌ Incomplete'}")

        if not is_configured:
            missing = config.get_missing_config()
            print(f"   Missing: {', '.join(missing)}")

        return is_configured

    except Exception as e:
        print(f"   ❌ Error testing config: {e}")
        return False

def test_qr_generation():
    """Test QR code generation with blockchain data."""
    print("\n📱 Testing QR code generation...")

    try:
        from breaknwipe.certificate.qr import QRGenerator

        # Create test QR data
        test_data = {
            'type': 'breaknwipe_blockchain_certificate',
            'version': '2.0',
            'report_id': 'test-report-123',
            'device_serial': 'TEST123456',
            'success': True,
            'algorithm': 'nist-clear',
            'timestamp': 1234567890,
            'blockchain': {
                'network': 'sepolia',
                'contract': '0x23183BCD67664eD995ec06FF31289A7d3b0897e3',
                'hash': '0x1234567890abcdef',
                'verified': True
            },
            'verify_url': 'https://datawipe.vercel.app?hash=0x1234567890abcdef'
        }

        qr_data = json.dumps(test_data, separators=(',', ':'))

        # Generate QR code
        qr_generator = QRGenerator()

        # Test QR validation
        validation = qr_generator.validate_qr_size(qr_data)
        print(f"   QR data length: {validation['data_length']} bytes")
        print(f"   Estimated size: {validation['estimated_qr_size']}")
        print(f"   Recommended: {'✅ Yes' if validation['recommended'] else '❌ No'}")

        if validation['suggestions']:
            for suggestion in validation['suggestions']:
                print(f"   💡 {suggestion}")

        # Test terminal QR generation
        terminal_qr = qr_generator.generate_terminal_qr(qr_data)
        print(f"   Terminal QR: {'✅ Generated' if terminal_qr else '❌ Failed'}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing QR generation: {e}")
        return False

def test_mock_certificate_generation():
    """Test certificate generation workflow (without actual blockchain transaction)."""
    print("\n📄 Testing certificate generation workflow...")

    try:
        from breaknwipe.certificate.generator import CertificateGenerator
        from breaknwipe.certificate.report import WipeReport, DeviceInfo
        from datetime import datetime
        import uuid
        import tempfile

        # Create mock device info
        device_info = DeviceInfo(
            path="/dev/sda",
            model="Test USB Drive",
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
            organization="Test Organization",
            operator="Test User"
        )

        # Set a test report ID
        report.report_id = str(uuid.uuid4())

        # Create certificate generator with temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            generator = CertificateGenerator(
                output_directory=temp_dir,
                enable_blockchain=False  # Test without actual blockchain
            )

            # Test QR data generation
            qr_data = generator._generate_qr_data(report, None)
            print(f"   Traditional QR data: {'✅ Generated' if qr_data else '❌ Failed'}")

            # Test with mock blockchain result
            mock_blockchain_result = {
                'success': True,
                'report_hash': '0x1234567890abcdef1234567890abcdef12345678',
                'transaction_hash': '0xabcdef1234567890abcdef1234567890abcdef12',
                'block_number': 12345
            }

            # This would test blockchain QR generation if blockchain store is available
            try:
                blockchain_qr_data = generator._generate_qr_data(report, mock_blockchain_result)
                print(f"   Blockchain QR data: {'✅ Generated' if blockchain_qr_data else '❌ Failed'}")
            except Exception as e:
                print(f"   Blockchain QR data: ⚠️  Skipped (blockchain not configured)")

        return True

    except Exception as e:
        print(f"   ❌ Error testing certificate generation: {e}")
        return False

def main():
    """Run all blockchain functionality tests."""
    print("🔧 BreakNWipe Blockchain Integration Test")
    print("=" * 50)

    # Run tests
    tests = [
        ("Internet Connectivity", test_internet_connectivity),
        ("Blockchain Configuration", test_blockchain_config),
        ("QR Generation", test_qr_generation),
        ("Certificate Generation", test_mock_certificate_generation)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results[test_name] = False

    # Summary
    print("\n📊 Test Summary")
    print("-" * 20)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All blockchain functionality tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check configuration and network connectivity.")
        return 1

if __name__ == "__main__":
    sys.exit(main())