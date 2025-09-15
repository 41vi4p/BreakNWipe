#!/bin/bash
#
# BreakNWipe Demonstration Script
# Shows the capabilities of BreakNWipe secure data wiping utility
#

set -e

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
PURPLE='\\033[0;35m'
CYAN='\\033[0;36m'
NC='\\033[0m' # No Color

# Functions
print_header() {
    echo
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo
}

print_section() {
    echo
    echo -e "${PURPLE}--- $1 ---${NC}"
    echo
}

print_status() {
    echo -e "${CYAN}[DEMO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

wait_for_user() {
    echo
    read -p "Press Enter to continue or Ctrl+C to exit..."
    echo
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This demonstration requires root privileges"
        echo "Usage: sudo ./demo.sh"
        exit 1
    fi
}

demo_banner() {
    clear
    print_header "BreakNWipe v1.0.0 - Demonstration"
    echo -e "${CYAN}Comprehensive Secure Data Wiping for IT Asset Recycling${NC}"
    echo -e "${GREEN}Developed by CodeBreakers Team${NC}"
    echo
    echo -e "${YELLOW}This demonstration will show you:${NC}"
    echo "  • Available wiping algorithms and standards"
    echo "  • Device detection and analysis"
    echo "  • Certificate generation with QR codes"
    echo "  • Safe simulation mode (no actual wiping)"
    echo "  • Command-line interface features"
    echo
    print_warning "This is a SAFE demonstration - no data will be wiped"
    wait_for_user
}

demo_help() {
    print_section "1. Help and Version Information"

    print_status "Showing BreakNWipe help information..."
    python -m breaknwipe.cli.main --help

    echo
    print_status "Showing version information..."
    python -m breaknwipe.cli.main --version || echo "BreakNWipe v1.0.0"

    wait_for_user
}

demo_algorithms() {
    print_section "2. Available Wiping Algorithms"

    print_status "Listing all available wiping algorithms..."
    python -m breaknwipe.cli.main list-algorithms

    echo
    print_status "Algorithm details from engine..."
    python -c "
from breaknwipe.wipe_engine.algorithms import list_available_algorithms
import json

algorithms = list_available_algorithms()
print('\\nSupported algorithms:')
for algo in algorithms:
    print(f'  • {algo[\"type\"]}: {algo[\"name\"]} ({algo[\"passes\"]} passes)')
    print(f'    Category: {algo[\"category\"]} | SSD Safe: {\"Yes\" if algo[\"ssd_safe\"] else \"No\"}')
    print()
"

    wait_for_user
}

demo_device_detection() {
    print_section "3. Device Detection and Analysis"

    print_status "Detecting available storage devices..."
    python -m breaknwipe.cli.main --list-devices

    echo
    print_status "Detailed device detection with Python API..."
    python -c "
from breaknwipe.device.detector import DeviceDetector

detector = DeviceDetector()
devices = detector.list_devices()

print(f'\\nFound {len(devices)} storage device(s):\\n')

for device in devices:
    print(f'Device: {device.path}')
    print(f'  Model: {device.model}')
    print(f'  Capacity: {device.capacity_human}')
    print(f'  Type: {device.device_type.value}')
    print(f'  Interface: {device.interface.value}')
    print(f'  Mounted: {\"Yes\" if device.is_mounted else \"No\"}')
    print(f'  Recommended Algorithm: {device.recommended_algorithm}')
    print(f'  Hardware Erase Support: {\"Yes\" if device.supports_hardware_erase else \"No\"}')

    warnings = device.get_wipe_warnings()
    if warnings:
        print('  Warnings:')
        for warning in warnings:
            print(f'    - {warning}')
    print()
"

    wait_for_user
}

demo_device_info() {
    print_section "4. Device Information Details"

    # Try to get info for first available device
    local device_path
    device_path=$(python -c "
from breaknwipe.device.detector import DeviceDetector
detector = DeviceDetector()
devices = detector.list_devices()
if devices:
    print(devices[0].path)
" 2>/dev/null || echo "")

    if [[ -n "$device_path" && -e "$device_path" ]]; then
        print_status "Getting detailed information for device: $device_path"
        python -m breaknwipe.cli.main info "$device_path"
    else
        print_warning "No suitable device found for detailed analysis"
        print_status "Here's how device info would look:"
        echo "
Device Information: /dev/sda
Model: Samsung SSD 980 PRO 1TB
Serial: S6J2NX0W123456A
Capacity: 1.0 TB
Type: ssd_nvme
Interface: nvme
Secure Erase Support: Yes
"
    fi

    wait_for_user
}

demo_dry_run() {
    print_section "5. Safe Simulation (Dry Run)"

    local device_path
    device_path=$(python -c "
from breaknwipe.device.detector import DeviceDetector
detector = DeviceDetector()
devices = detector.list_devices()
# Find a safe device (not mounted, not system)
for device in devices:
    if not device.is_mounted and not device.is_system_disk:
        print(device.path)
        break
" 2>/dev/null || echo "")

    if [[ -n "$device_path" && -e "$device_path" ]]; then
        print_status "Running safe simulation on device: $device_path"
        print_warning "This will NOT actually wipe any data (dry-run mode)"

        echo
        print_status "Simulating NIST Clear algorithm..."
        timeout 30 python -m breaknwipe.cli.main wipe \\
            --device "$device_path" \\
            --algorithm nist-clear \\
            --dry-run \\
            --certificate \\
            --output ./demo_reports/ || true

    else
        print_warning "No suitable device found for simulation"
        print_status "Simulation would show:"
        echo "
✓ Device validation passed
✓ Algorithm: NIST SP 800-88 Clear (1 pass)
✓ Estimated time: 2 hours 15 minutes
✓ Simulating pass 1/1: Zero fill
✓ Progress: [████████████████████████████████████] 100%
✓ Verification: PASSED
✓ Certificate generated: BreakNWipe_Certificate_abc123.pdf
"
    fi

    wait_for_user
}

demo_certificate() {
    print_section "6. Certificate Generation"

    print_status "Demonstrating certificate and QR code generation..."

    # Create a demo report
    python -c "
import json
import time
from breaknwipe.certificate.report import WipeReport, DeviceInfo, WipePassResult, VerificationResult
from breaknwipe.certificate.generator import CertificateGenerator
from breaknwipe.certificate.qr import QRGenerator

# Create demo data
device_info = DeviceInfo(
    path='/dev/demo',
    model='Demo Storage Device 1TB',
    serial='DEMO123456789',
    capacity_bytes=1000000000000,
    capacity_human='1.0 TB',
    device_type='ssd_sata',
    interface='sata',
    vendor='Demo Corp'
)

# Create demo report
report = WipeReport(
    device_info=device_info,
    algorithm_used='NIST SP 800-88 Clear',
    wipe_method='software',
    start_time=time.time() - 3600,  # 1 hour ago
    end_time=time.time(),
    total_passes=1,
    success=True,
    total_bytes_written=1000000000000,
    standards_compliance=['NIST SP 800-88']
)

# Add pass result
pass_result = WipePassResult(
    pass_number=1,
    algorithm='nist-clear',
    pattern_description='NIST Clear - Zero fill',
    start_time=report.start_time,
    end_time=report.end_time,
    bytes_written=report.total_bytes_written,
    success=True
)
report.add_pass_result(pass_result)

# Add verification
verification = VerificationResult(
    verification_type='comprehensive',
    passed=True,
    entropy_score=0.1,
    sample_count=100
)
report.set_verification_result(verification)

# Generate certificates
import os
os.makedirs('./demo_reports', exist_ok=True)

generator = CertificateGenerator('./demo_reports')
files = generator.generate_certificate(report)

print('Certificate generation demonstration:')
for format_type, file_path in files.items():
    print(f'  ✓ {format_type.upper()}: {file_path}')

# Generate QR code for terminal
qr_gen = QRGenerator()
qr_data = qr_gen.create_verification_qr_data(
    report.report_id,
    report.certificate_hash or 'demo_hash_123456'
)

print('\\nQR Code for Certificate Verification:')
qr_gen.display_terminal_qr(qr_data, 'Certificate Verification QR Code')
"

    wait_for_user
}

demo_interactive() {
    print_section "7. Interactive Mode Preview"

    print_status "Interactive mode provides a guided wizard interface..."
    print_status "Here's what the interactive mode looks like:"

    echo
    echo -e "${GREEN}BreakNWipe v1.0.0${NC}"
    echo -e "${GREEN}Secure Data Wiping for IT Asset Recycling${NC}"
    echo
    echo "Welcome to BreakNWipe Interactive Mode!"
    echo
    echo "Step 1: Device Selection"
    echo "  Available devices:"
    echo "    1. /dev/sda - Samsung SSD 980 (1.0 TB) [Available]"
    echo "    2. /dev/sdb - WD Blue HDD (2.0 TB) [Mounted]"
    echo "    3. /dev/nvme0n1 - Intel Optane (512 GB) [Available]"
    echo
    echo "Step 2: Algorithm Selection"
    echo "  Recommended algorithms for your device:"
    echo "    1. NIST SP 800-88 Clear (1 pass) - Fast, government standard"
    echo "    2. NIST SP 800-88 Purge (3 passes) - More secure"
    echo "    3. DoD 5220.22-M (3 passes) - Military standard"
    echo
    echo "Step 3: Verification and Certification"
    echo "  • Verify wipe completion: Yes"
    echo "  • Generate certificate: Yes (PDF + JSON)"
    echo "  • Include QR code: Yes"
    echo
    echo "Step 4: Final Confirmation"
    echo "  • Device: /dev/sda (Samsung SSD 980)"
    echo "  • Algorithm: NIST Clear"
    echo "  • Estimated time: 45 minutes"
    echo "  • This will PERMANENTLY DESTROY all data!"
    echo
    print_warning "To launch interactive mode: sudo breaknwipe --interactive"

    wait_for_user
}

demo_batch_processing() {
    print_section "8. Batch Processing"

    print_status "Creating demo batch configuration..."

    cat > ./demo_batch_config.json << EOF
{
  "devices": [
    {
      "path": "/dev/demo1",
      "algorithm": "nist-clear",
      "verify": true,
      "note": "Laptop drive from R&D"
    },
    {
      "path": "/dev/demo2",
      "algorithm": "dod-3pass",
      "verify": true,
      "note": "Server drive with sensitive data"
    }
  ],
  "output_dir": "./batch_reports/",
  "parallel": 2,
  "organization": "Demo Company",
  "operator": "IT Admin",
  "location": "Data Center A"
}
EOF

    print_success "Batch configuration created: demo_batch_config.json"
    echo
    print_status "Batch configuration contents:"
    cat ./demo_batch_config.json

    echo
    print_status "To run batch processing:"
    echo "  sudo breaknwipe batch --config demo_batch_config.json"

    wait_for_user
}

demo_verification() {
    print_section "9. Certificate Verification"

    print_status "Certificate verification ensures authenticity..."

    # Check if we have any demo certificates
    if [[ -f "./demo_reports/"*".json" ]]; then
        local cert_file
        cert_file=$(find ./demo_reports/ -name "*.json" -type f | head -1)

        if [[ -n "$cert_file" ]]; then
            print_status "Verifying certificate: $cert_file"
            python -m breaknwipe.cli.main verify-certificate --cert-file "$cert_file"
        fi
    else
        print_status "Certificate verification would show:"
        echo "
Verifying certificate: BreakNWipe_Certificate_abc123.json
✓ Certificate file found
✓ JSON format valid
✓ Digital signature verified
✓ Hash verification passed
✓ Certificate is authentic and unmodified

Certificate Details:
  • Report ID: abc123-def456-ghi789
  • Device: Samsung SSD 980 (DEMO123456789)
  • Algorithm: NIST SP 800-88 Clear
  • Status: PASSED
  • Generated: 2025-01-15 14:30:25 UTC
"
    fi

    wait_for_user
}

demo_summary() {
    print_header "Demonstration Complete!"

    echo -e "${GREEN}You've seen all major features of BreakNWipe:${NC}"
    echo
    echo "✓ Standards-compliant wiping algorithms (NIST, DoD, Gutmann)"
    echo "✓ Comprehensive device detection and analysis"
    echo "✓ Hardware-level secure erase support"
    echo "✓ PDF and JSON certificate generation"
    echo "✓ QR codes for easy verification"
    echo "✓ Interactive wizard and expert CLI modes"
    echo "✓ Batch processing capabilities"
    echo "✓ Digital signature verification"
    echo "✓ Safe dry-run simulation"
    echo
    echo -e "${BLUE}Key Benefits:${NC}"
    echo "• Builds trust in IT asset recycling"
    echo "• Meets government and industry standards"
    echo "• Provides tamper-proof evidence"
    echo "• Supports India's circular economy goals"
    echo "• Reduces e-waste hoarding"
    echo
    echo -e "${YELLOW}Quick Start Commands:${NC}"
    echo "• ${GREEN}sudo breaknwipe --interactive${NC}     # Guided wizard"
    echo "• ${GREEN}sudo breaknwipe --list-devices${NC}    # See available devices"
    echo "• ${GREEN}breaknwipe --help${NC}                 # Full command help"
    echo
    echo -e "${PURPLE}Installation Options:${NC}"
    echo "• ${GREEN}make install-system${NC}              # Install system-wide"
    echo "• ${GREEN}make package${NC}                     # Build .deb/.rpm packages"
    echo "• ${GREEN}pip install breaknwipe${NC}           # Install from PyPI (future)"
    echo
    echo -e "${CYAN}For production use, always:${NC}"
    echo "• Verify device paths before wiping"
    echo "• Use appropriate algorithms for your compliance needs"
    echo "• Keep certificates for audit trails"
    echo "• Test with --dry-run first"
    echo
    echo -e "${GREEN}Thank you for trying BreakNWipe!${NC}"
    echo -e "${GREEN}Making India's e-waste recycling safer and more trustworthy.${NC}"
    echo
    echo -e "${BLUE}Proudly developed by the CodeBreakers Team:${NC}"
    echo "David Porathur • Blaise Rodrigues • Vanessa Rodrigues"
    echo "Natasha Lewis • Chris Lopes • Anastasia Lopes"
    echo
}

cleanup_demo() {
    print_status "Cleaning up demonstration files..."
    rm -f ./demo_batch_config.json
    # Keep demo_reports for user to examine
    if [[ -d "./demo_reports" ]]; then
        print_status "Demo reports saved in: ./demo_reports/"
        print_status "You can examine the generated certificates and delete when done."
    fi
}

# Main demonstration
main() {
    check_root
    demo_banner
    demo_help
    demo_algorithms
    demo_device_detection
    demo_device_info
    demo_dry_run
    demo_certificate
    demo_interactive
    demo_batch_processing
    demo_verification
    demo_summary
    cleanup_demo
}

# Run main function
main "$@"