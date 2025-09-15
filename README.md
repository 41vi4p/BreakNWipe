# BreakNWipe - Comprehensive Data Wiping CLI Utility

A robust, secure, and standards-compliant data wiping solution designed to address India's e-waste crisis by providing trustworthy IT asset recycling through secure data sanitization.

## 🎯 Problem Statement

India generates over 1.75 million tonnes of e-waste annually. A key barrier to responsible recycling is fear of data breaches, leading to over ₹50,000 crore worth of IT assets being hoarded instead of properly recycled. BreakNWipe solves this by providing:

- **Secure data erasure** including hidden areas (HPA/DCO, SSD sectors)
- **Tamper-proof certificates** (PDF and JSON formats)
- **One-click interface** suitable for general public use
- **Offline capability** (bootable ISO/USB support)
- **Third-party verification** of wipe status
- **Standards compliance** (NIST SP 800-88, IEEE 2883:2022)

## ✨ Features

### 🔒 Security Standards
- **NIST SP 800-88 Rev 1** (Clear/Purge methods)
- **IEEE 2883:2022** (Latest sanitization standard)
- **DoD 5220.22-M** (3-pass and 7-pass variants)
- **Gutmann Method** (35-pass for legacy drives)
- **Hardware-level erasure** (ATA Secure Erase, NVMe Sanitize)

### 💾 Device Support
- Traditional HDDs (magnetic storage)
- SATA SSDs with ATA Secure Erase
- NVMe drives with sanitize commands
- USB flash drives and memory cards
- Special area handling (HPA/DCO, bad sectors)

### 📋 Certification & Verification
- Digitally signed PDF certificates
- JSON reports for automated processing
- QR codes for instant verification
- Tamper-proof audit trails
- Third-party verification support

### 🖥️ User Interface
- **Interactive Mode**: Guided wizard for beginners
- **Expert Mode**: Full command-line control
- **Batch Processing**: Multiple device automation
- **Real-time Progress**: Speed, ETA, and status updates

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (when available)
pip install breaknwipe

# Or install from source
git clone https://github.com/breaknwipe/breaknwipe.git
cd breaknwipe
pip install -e .
```

### Basic Usage

```bash
# Interactive mode (recommended for beginners)
sudo breaknwipe --interactive

# List available devices
sudo breaknwipe --list-devices

# Quick wipe with NIST Clear standard
sudo breaknwipe wipe --device /dev/sda --algorithm nist-clear --certificate

# Expert mode with verification
sudo breaknwipe wipe --device /dev/sda --algorithm dod-3pass --verify --output ./reports/
```

### Safety First 🛡️

```bash
# Always check device information first
sudo breaknwipe info /dev/sda

# Use dry-run to test without actually wiping
sudo breaknwipe wipe --device /dev/sda --algorithm nist-clear --dry-run
```

## 📖 Documentation

### Available Commands

| Command | Description |
|---------|-------------|
| `wipe` | Perform secure data wiping |
| `info` | Display device information |
| `list-algorithms` | Show available wiping algorithms |
| `batch` | Batch processing from config file |
| `verify-certificate` | Verify wipe certificate authenticity |

### Wiping Algorithms

| Algorithm | Passes | Description | Use Case |
|-----------|--------|-------------|----------|
| `nist-clear` | 1 | NIST SP 800-88 Clear method | General purpose |
| `nist-purge` | 3 | NIST SP 800-88 Purge method | High security |
| `dod-3pass` | 3 | DoD 5220.22-M standard | Government compliance |
| `dod-7pass` | 7 | Enhanced DoD standard | Maximum security |
| `gutmann` | 35 | Gutmann research method | Legacy drives |
| `random` | Variable | Random data overwrite | Configurable security |
| `zeros` | 1 | Zero-fill method | Quick sanitization |

### Certificate Features

- **Device identification**: Serial number, model, capacity
- **Wipe details**: Algorithm used, timestamps, parameters
- **Verification**: Cryptographic hash verification
- **Digital signature**: Tamper-proof authenticity
- **QR code**: Quick verification and audit trail
- **Standards compliance**: NIST/DoD/IEEE certification

## 🔧 Advanced Usage

### Batch Processing

Create a configuration file:

```json
{
  "devices": [
    {
      "path": "/dev/sda",
      "algorithm": "nist-purge",
      "verify": true
    },
    {
      "path": "/dev/sdb",
      "algorithm": "dod-3pass",
      "verify": true
    }
  ],
  "output_dir": "./batch_reports/",
  "parallel": 2
}
```

Run batch processing:

```bash
sudo breaknwipe batch --config batch_config.json
```

### Custom Algorithms

```bash
# Custom random passes
sudo breaknwipe wipe --device /dev/sda --algorithm random --passes 5

# Custom pattern (advanced users)
sudo breaknwipe wipe --device /dev/sda --algorithm custom --passes 3
```

## ⚠️ Important Warnings

- **⚠️ DATA DESTRUCTION**: All data will be permanently destroyed
- **🔒 ROOT REQUIRED**: Must run with sudo/root privileges
- **💾 UNMOUNT FIRST**: Unmount filesystems before wiping
- **🔌 POWER STABLE**: Ensure stable power during operation
- **🌡️ TEMPERATURE**: Monitor drive temperature during long wipes
- **💿 RAID ARRAYS**: Handle RAID configurations with extreme care

## 🏗️ Architecture

```
breaknwipe/
├── wipe_engine/     # Core wiping algorithms and engine
├── device/          # Device detection and hardware handling
├── certificate/     # Certificate generation and verification
├── cli/            # Command-line interface
└── tests/          # Test suites and validation
```

## 📊 Performance

| Drive Type | Algorithm | Speed (Typical) | Time (1TB) |
|------------|-----------|-----------------|------------|
| HDD 7200 RPM | NIST Clear | 150 MB/s | ~2 hours |
| SSD SATA | ATA Secure Erase | 500 MB/s | ~30 minutes |
| NVMe SSD | NVMe Sanitize | 2000 MB/s | ~8 minutes |
| USB 3.0 | Random 3-pass | 50 MB/s | ~17 hours |

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/breaknwipe/breaknwipe.git
cd breaknwipe
pip install -e ".[dev]"
pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏛️ Standards Compliance

- **NIST SP 800-88 Rev 1**: U.S. Federal media sanitization guidelines
- **IEEE 2883:2022**: Standard for sanitization of storage
- **Common Criteria**: Protection profiles for secure deletion
- **ISO/IEC 27040**: Storage security guidelines
- **BSI TL-03423**: German federal security standards

## 🌟 Impact

By providing trustworthy data sanitization, BreakNWipe aims to:

- **Reduce e-waste hoarding** by building user confidence
- **Promote circular economy** through safe device recycling
- **Support India's environmental goals** and reduce electronic waste
- **Enable secure IT asset disposal** for businesses and individuals
- **Create trust** in the recycling ecosystem

## 📞 Support

- 📖 **Documentation**: [https://breaknwipe.readthedocs.io/](https://breaknwipe.readthedocs.io/)
- 🐛 **Issues**: [GitHub Issues](https://github.com/breaknwipe/breaknwipe/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/breaknwipe/breaknwipe/discussions)
- 📧 **Contact**: contact@breaknwipe.org

---

**🇮🇳 Made for India's e-waste solution | 🌍 Promoting global circular economy**