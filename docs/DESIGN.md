# BreakNWipe - Comprehensive Data Wiping CLI Utility

## Architecture Overview

### Core Components

1. **Wipe Engine** (`wipe_engine/`)
   - Algorithm implementations (DoD, NIST, Gutmann, etc.)
   - Storage device detection and handling
   - Progress tracking and verification

2. **Device Handler** (`device/`)
   - HDD/SSD/NVMe detection
   - ATA Secure Erase support
   - NVMe sanitize commands
   - Device capability assessment

3. **Certificate Generator** (`certificate/`)
   - PDF report generation with digital signatures
   - JSON report export
   - QR code generation for verification
   - Tamper-proof evidence chain

4. **CLI Interface** (`cli/`)
   - Interactive wizard mode
   - Expert command-line mode
   - Progress display and logging

## Supported Algorithms

### Standard Compliant
- **NIST SP 800-88 Rev 1** (Clear/Purge methods)
- **IEEE 2883:2022** (Latest standard support)
- **DoD 5220.22-M** (3-pass and 7-pass variants)

### Legacy/Research Methods
- **Gutmann Method** (35-pass for legacy drives)
- **Schneier Algorithm** (7-pass)
- **Random Overwrite** (configurable passes)
- **Zero Fill** (single pass)

### Hardware-Level
- **ATA Secure Erase** (Built-in drive firmware)
- **NVMe Format/Sanitize** (NVMe specification)
- **TRIM/Discard** (SSD optimization)

## Device Support

### Storage Types
- Traditional HDDs (magnetic)
- SATA SSDs
- NVMe SSDs
- USB flash drives
- SD cards and memory cards
- RAID arrays (with appropriate warnings)

### Special Areas
- Host Protected Area (HPA)
- Device Configuration Overlay (DCO)
- Bad sector remapping areas
- Wear leveling reserve areas

## CLI Interface Design

### Interactive Mode (Beginner)
```bash
breaknwipe --interactive
# Guided wizard with device selection, algorithm choice, and safety confirmations
```

### Expert Mode
```bash
breaknwipe --device /dev/sda --algorithm nist-clear --verify --certificate
```

### Batch Mode
```bash
breaknwipe --config batch_config.json --output reports/
```

## Certificate Features

### PDF Certificate
- Device identification (serial, model, capacity)
- Algorithm used and parameters
- Start/end timestamps
- Verification results
- Digital signature with timestamp
- QR code for online verification

### JSON Report
- Machine-readable format
- Audit trail information
- Performance metrics
- Error logs and warnings

## Security Features

### Verification
- Read-back verification of wiped data
- Cryptographic hashing of wipe patterns
- Pre/post wipe device state comparison

### Tamper Evidence
- Digital signatures using cryptographic keys
- Blockchain-like verification chain
- Immutable audit logs

## Technical Requirements

### Dependencies
- Python 3.8+ (main implementation)
- `cryptography` library (for signatures)
- `reportlab` (PDF generation)
- `qrcode` (QR code generation)
- `psutil` (system information)
- `click` (CLI framework)

### System Requirements
- Linux kernel 4.0+ (for NVMe support)
- Root privileges (for direct device access)
- Internet connection (optional, for certificate verification)

## Safety Features

### Pre-wipe Checks
- Device type detection
- Mounted filesystem warnings
- RAID member detection
- Power management settings
- Temperature monitoring

### Progress Monitoring
- Real-time progress display
- ETA calculation
- Speed monitoring
- Error detection and reporting

### Emergency Features
- Graceful interrupt handling
- Resume capability for interrupted wipes
- Emergency stop functionality
- Log preservation

## Compliance and Standards

### Regulatory Compliance
- NIST SP 800-88 Rev 1 (US Federal)
- Common Criteria Protection Profiles
- ISO/IEC 27040 (Storage security)
- IEEE 2883:2022 (Data sanitization)

### Industry Standards
- BSI TL-03423 (German Federal)
- CESG CPA (UK Government)
- ANSSI-CC-cible_commune (French)
- DIN 66399 (German destruction standards)

## Performance Optimization

### Multi-threading
- Parallel verification
- Background certificate generation
- Asynchronous progress reporting

### Hardware Optimization
- Native ATA commands when available
- DMA vs PIO mode selection
- Buffer size optimization
- Thermal throttling awareness

## Installation and Distribution

### Package Management
- Debian/Ubuntu .deb packages
- RPM packages for RHEL/Fedora
- PyPI distribution
- Docker container image

### Portable Mode
- Self-contained executable
- USB bootable image
- Live CD/DVD creation scripts