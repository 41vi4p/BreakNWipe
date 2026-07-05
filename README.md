<div align="center">

<img src="frontend_ui/images/logo.png" alt="BreakNWipe Logo" width="120"/>

# BreakNWipe

**A one-click solution to *Break* the data through randomized encryption and *Wipe* it leaving no traces behind.**

[![Version](https://img.shields.io/badge/version-2.8.2-blue.svg)](docs/CHANGELOG.md)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-FCC624.svg?logo=linux&logoColor=black)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web%20GUI-009688.svg?logo=fastapi&logoColor=white)](#%EF%B8%8F-user-interfaces)
[![Solidity](https://img.shields.io/badge/Solidity-Sepolia%20Testnet-363636.svg?logo=solidity&logoColor=white)](#-blockchain-verification)
[![NIST SP 800-88](https://img.shields.io/badge/NIST-SP%20800--88-orange.svg)](#-standards-compliance)
[![SIH 2025](https://img.shields.io/badge/Smart%20India%20Hackathon-2025-FF6B35.svg)](#-about-the-project)

</div>

---

**Quick Links:** [Features](#-features) • [How It Works](#-how-it-works) • [Quick Start](#-quick-start) • [Blockchain Verification](#-blockchain-verification) • [Standards Compliance](#-standards-compliance) • [Important Warnings](#-important-warnings) • [Development](#-development) • [License](#-license)

---

**Install via APT** (Ubuntu/Debian, x86_64 — [details](#installation), one-time repo setup, then `apt upgrade` handles updates forever):

```bash
curl -fsSL https://41vi4p.github.io/BreakNWipe/apt/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/breaknwipe.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/breaknwipe.gpg] https://41vi4p.github.io/BreakNWipe/apt stable main" | sudo tee /etc/apt/sources.list.d/breaknwipe.list
sudo apt update && sudo apt install breaknwipe
```

**Or install via the one-liner script** ([details](#installation)):

```bash
curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/quickstart.sh | sudo bash
```

**Uninstall** ([details](#uninstallation)):

```bash
curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/uninstall.sh -o breaknwipe-uninstall.sh && sudo bash breaknwipe-uninstall.sh
```

---

## 🏆 About the Project

BreakNWipe was built for **Smart India Hackathon 2025** by **Team CodeBreakers!**

| | |
|---|---|
| **Problem Statement ID** | SIH25070 |
| **Problem Statement** | Secure Data Wiping for Trustworthy IT Asset Recycling |
| **Theme** | Miscellaneous |
| **Category** | Software |
| **Team ID** | 65891 |
| **Team Name** | CodeBreakers! |

### The Problem

India generates over **1.75 million tonnes of e-waste annually**. A key barrier to responsible recycling is the fear of data breaches, which leads to over **₹50,000 crore worth of IT assets** being hoarded instead of properly recycled. BreakNWipe builds trust in the recycling ecosystem by making data sanitization verifiable, standards-compliant, and simple enough for the general public.

### Why We're Different

BreakNWipe doesn't just overwrite data — it uses a three-layer defense:

1. **🔐 Randomized Encryption Algorithm (REA)** — data is first encrypted on-the-fly with randomized keys and multi-chain encryption, making it *unreadable*
2. **🔑 Secure Key Destruction** — encryption keys are destroyed, making the data *undecryptable*
3. **📝 Overwriting** — one of seven industry-standard overwrite algorithms makes the data *unrecoverable*

And the result isn't just a wiped drive — it's **proof anyone can independently verify**: a digitally signed PDF/JSON certificate with a QR code, anchored on a public blockchain.

## ⚙️ How It Works

```
   PRE-WIPE                      WIPING                        POST-WIPE
┌─────────────────┐   ┌───────────────────────────┐   ┌────────────────────────┐
│ Launch software │   │ Quick Wipe: 1-pass        │   │ PDF / JSON report      │
│ Detect drives & │ → │  one-click for the public │ → │ Blockchain + QR proof  │
│ hidden areas    │   │ Deep Wipe: REA encryption │   │ Third-party verifiable │
│ (HPA/DCO/bad    │   │  + multipass overwrite    │   │ Device safe to discard │
│  blocks)        │   │  (7 algorithms)           │   │ Data 100% irrecoverable│
└─────────────────┘   └───────────────────────────┘   └────────────────────────┘
```

## ✨ Features

### ✅ Implemented

#### Wiping Engine
- [x] **7 overwrite algorithms** — NIST Clear, NIST Purge, DoD 3-Pass, DoD 7-Pass, Gutmann 35-Pass, Random, Zero-fill (+ fully custom)
- [x] **REA Cryptographic Erase** — `rea-basic`, `rea-multichain`, `rea-extreme`, `rea-fast`, `rea-custom` (randomized encryption + key destruction + overwrite)
- [x] **Hardware-level erasure** — ATA Secure Erase and NVMe Sanitize/Format commands
- [x] **Read-back verification** of wiped data with per-block validation
- [x] **Dry-run mode** for safe testing

#### Device Support
- [x] HDDs, SATA SSDs, NVMe drives, USB flash drives and memory cards
- [x] **Hidden area detection** — HPA (Host Protected Area) and DCO (Device Configuration Overlay) via `hdparm`
- [x] Android device wiping via **ADB** (encrypts before factory reset — stronger than a plain factory reset)
- [x] Drive temperature monitoring during long wipes

#### Disk Utility Toolkit
- [x] **Drive health dashboard** — SMART status, temperature, power-on hours, and (where a reliable source exists — NVMe's standardized wear indicator or a recognized SATA SSD wear attribute) an estimated remaining-lifespan percentage; honestly reports "not available" rather than a guess for HDDs and unrecognized SSDs. Available via `breaknwipe info <device>` and the web GUI's "Details / Health / Repair" page.
- [x] **Partition browsing** — filesystem type, size, and mount point per partition, in both the CLI (`breaknwipe info <device>`) and the web GUI
- [x] **Filesystem repair (fsck)** — checks (and, with `--repair`, fixes) ext2/3/4, FAT/exFAT, NTFS, XFS, and Btrfs filesystems, with a safety model that never auto-unmounts and gates repairing system/Btrfs filesystems behind `--force`. Available as `breaknwipe fsck <partition>` and from each device's web GUI details page.

#### Certification & Verification
- [x] **Digitally signed PDF certificates** (RSA / X.509)
- [x] **JSON reports** for automated processing
- [x] **QR codes** for instant verification
- [x] **Blockchain anchoring** — certificates stored on Ethereum Sepolia via the `ReportRegistryWithJson` smart contract
- [x] **Online QR verification** through the [datawipe webapp](https://datawipe.vercel.app) (scan → cross-check on blockchain → tamper-proof report)
- [x] Audit-trail logging to a local database

#### User Interfaces
- [x] **Interactive CLI wizard** for beginners (`--interactive`)
- [x] **Expert CLI mode** with full command-line control
- [x] **Web GUI** — FastAPI + WebSocket interface with real-time progress, speed, and ETA (`--gui`)
- [x] **Batch processing** of multiple devices from a config file
- [x] `.deb` / `.rpm` package build scripts and system installer
- [x] **Self-hosted APT repository** (GitHub Pages) — `sudo apt install breaknwipe` with real updates via `apt upgrade`

### 🚧 Planned / Not Yet Implemented

- [ ] **EDL mode wiping** for Qualcomm chipsets (requires QFIL integration)
- [ ] **SP Flash Tool mode** for MediaTek chipsets
- [ ] **Odin download mode** for Samsung chipsets
- [ ] **Bootable ISO/USB** — standalone offline wiping environment (custom OS)
- [ ] **Windows support** (currently Linux-only)
- [ ] **Multilingual UI** with localized labels
- [ ] **PyPI release** (`pip install breaknwipe`)
- [ ] Resume capability for interrupted wipes
- [ ] Automated test suite with CI

## 🚀 Quick Start

### Installation

> **OS support:** everything below (the APT repo, `quickstart.sh`, `install_dependencies.sh`, `install.sh`, and `make install-system`) targets **Ubuntu/Debian on x86_64** — they shell out to `apt` for system packages (`hdparm`, `nvme-cli`, `smartmontools`, etc.). `uv sync` / `pip install -e .` on their own are platform-agnostic (any Linux/macOS with Python), but you'll still need to provide `hdparm`/`nvme-cli`/`smartmontools` yourself via your distro's package manager for device-level operations to work.

**APT repository (recommended)** — a real, signed APT repo self-hosted on GitHub Pages. One-time setup, then every future release is a normal `sudo apt update && sudo apt upgrade`, no re-running installer scripts:

```bash
curl -fsSL https://41vi4p.github.io/BreakNWipe/apt/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/breaknwipe.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/breaknwipe.gpg] https://41vi4p.github.io/BreakNWipe/apt stable main" | sudo tee /etc/apt/sources.list.d/breaknwipe.list
sudo apt update
sudo apt install breaknwipe
```

The package is fully self-contained (BreakNWipe + all its Python dependencies are vendored into a `uv`-managed virtual environment at build time), so it doesn't pull in a web of `python3-*` system packages — just the device tools BreakNWipe actually shells out to (`hdparm`, `nvme-cli`, `smartmontools`, `util-linux`). Built and published by [`.github/workflows/apt-repo.yml`](.github/workflows/apt-repo.yml) on every tagged release; see [`docs/APT_REPO_SETUP_GUIDE.md`](docs/APT_REPO_SETUP_GUIDE.md) for the one-time maintainer setup.

**One-liner script** — clones the repo and runs the full system installer (dedicated user, systemd service, `breaknwipe`/`bwipe` commands on PATH). As with any curl-to-bash installer, review the script before piping it into a root shell:

```bash
curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/quickstart.sh | sudo bash
```

**Or manually**, if you'd rather keep the checkout around for development:

```bash
# Clone the repository
git clone https://github.com/41vi4p/BreakNWipe.git
cd BreakNWipe

# Install system-level dependencies (hdparm, nvme-cli, smartmontools, uv itself, ...)
sudo ./scripts/install_dependencies.sh

# Then install Python dependencies with uv (creates a .venv from pyproject.toml/uv.lock)
uv sync

# Or install from source with pip instead of uv
pip install -e .
pip install -e ".[web,blockchain]"   # with optional extras

# Or full system-wide install (system deps + dedicated user + systemd service)
sudo make install-system
```

### Uninstallation

**If you installed via APT:**

```bash
sudo apt remove breaknwipe          # keep config/data
sudo apt purge breaknwipe           # also remove config/data
sudo rm /etc/apt/sources.list.d/breaknwipe.list   # stop tracking the repo entirely
```

**If you still have the repo cloned:**

```bash
sudo make uninstall-system
# or directly:
sudo ./scripts/uninstall.sh
```

**If you installed via the one-liner and don't have a local checkout anymore** — `uninstall.sh` is self-contained (it only touches system paths like `/opt/breaknwipe`, `/etc/breaknwipe`, `/usr/local/bin/breaknwipe`, so it doesn't need the repo present). Download it and run it directly:

```bash
curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/uninstall.sh -o breaknwipe-uninstall.sh
sudo bash breaknwipe-uninstall.sh
```

Note: unlike `quickstart.sh`, don't pipe this straight into `sudo bash` (`curl ... | sudo bash`) — it asks interactive yes/no confirmations before removing data and system dependencies, and those prompts don't work when the script's own text is occupying stdin. Download it to a file first, as above.

### Basic Usage

```bash
# Interactive mode (recommended for beginners)
sudo breaknwipe --interactive

# Launch the web GUI at http://127.0.0.1:8000
sudo breaknwipe --gui

# List available devices
sudo breaknwipe --list-devices

# Wipe with NIST Clear and generate a certificate
sudo breaknwipe wipe --device /dev/sdX --algorithm nist-clear --certificate

# Safety first: inspect the device and dry-run before wiping
sudo breaknwipe info /dev/sdX
sudo breaknwipe wipe --device /dev/sdX --algorithm nist-clear --dry-run
```

#### Shell Completion

Tab-completion (subcommands, `--algorithm`/`--filesystem` choices, and real `/dev/sd*`/`/dev/nvme*` device paths) is generated dynamically from the CLI itself, so it's always in sync with the real commands. `sudo apt install breaknwipe` and `sudo make install-system`/`scripts/install.sh` set this up automatically if `bash-completion` is installed. If you installed via `uv sync`/`pip install`, or use zsh/fish, set it up manually once:

```bash
# bash
_BREAKNWIPE_COMPLETE=bash_source breaknwipe > ~/.breaknwipe-complete.bash
echo 'source ~/.breaknwipe-complete.bash' >> ~/.bashrc

# zsh
_BREAKNWIPE_COMPLETE=zsh_source breaknwipe > ~/.breaknwipe-complete.zsh
echo 'source ~/.breaknwipe-complete.zsh' >> ~/.zshrc

# fish
_BREAKNWIPE_COMPLETE=fish_source breaknwipe > ~/.config/fish/completions/breaknwipe.fish
```

Restart your shell (or `source` the relevant rc file) afterward. To also complete the `bwipe` alias (bash only), add one more line after sourcing: `complete -o nosort -F _breaknwipe_completion bwipe`.

### Commands

| Command | Description |
|---------|-------------|
| `wipe` | Perform secure data wiping |
| `info <device>` | Display detailed device information, health, and partitions |
| `fsck <partition>` | Check (and, with `--repair`, fix) a filesystem's integrity |
| `list-algorithms` | Show available wiping algorithms |
| `batch` | Batch processing from a JSON/YAML config file |
| `verify-certificate` | Verify wipe certificate authenticity |

### Wiping Algorithms

| Algorithm | Passes | Description | Use Case |
|-----------|--------|-------------|----------|
| `nist-clear` | 1 | NIST SP 800-88 Clear | General purpose |
| `nist-purge` | 3 | NIST SP 800-88 Purge | High security |
| `dod-3pass` | 3 | DoD 5220.22-M | Government compliance |
| `dod-7pass` | 7 | Enhanced DoD | Maximum security |
| `gutmann` | 35 | Gutmann method | Legacy magnetic drives |
| `random` | Custom | Random data overwrite | Configurable security |
| `zeros` | 1 | Zero-fill | Quick sanitization |
| `custom` | Custom | User-defined patterns | Advanced users |
| `rea-*` | 1–7+ | Randomized Encryption Algorithm + overwrite | Deep Wipe (via Web GUI) |

## 🔗 Blockchain Verification

Every wipe certificate can be anchored on the **Ethereum Sepolia testnet**:

1. BreakNWipe completes the wipe and generates the signed certificate
2. The certificate hash (or full JSON) is stored on-chain via the `ReportRegistryWithJson` contract
3. A QR code embedding the blockchain reference is added to the PDF report
4. Anyone can scan the QR at **[datawipe.vercel.app](https://datawipe.vercel.app)** — the app queries the smart contract and displays the tamper-proof verification result

Setup details: [docs/BLOCKCHAIN_INTEGRATION.md](docs/BLOCKCHAIN_INTEGRATION.md)

```bash
# Configure your credentials (never commit the real .env!)
cp breaknwipe/.env.example breaknwipe/.env
cp blockchain/.env.example blockchain/.env
```

## 🏗️ Repository Structure

```
BreakNWipe/
├── breaknwipe/           # Python package
│   ├── wipe_engine/      #   Core wiping algorithms, REA, verification
│   ├── device/           #   Device detection, ATA/NVMe/mobile handlers
│   ├── certificate/      #   PDF/JSON certs, signatures, QR, blockchain
│   ├── cli/              #   Interactive & expert CLI, progress display
│   ├── web/              #   FastAPI server, WebSocket, session manager
│   └── logging/          #   Audit-trail logging service & database
├── blockchain/           # Hardhat project — ReportRegistryWithJson contract
├── frontend_ui/          # Web GUI static files (HTML/CSS)
├── docs/                 # Design docs, integration guides, SIH presentation
│   └── apt/pubkey.gpg    #   APT repo signing public key (see APT_REPO_SETUP_GUIDE.md)
├── scripts/              # Install, packaging, demo & setup scripts
├── tests/                # Integration test scripts
├── .github/workflows/    # CI: builds & publishes the APT repo on tagged releases
├── Makefile              # Development commands (make help)
├── pyproject.toml        # Package metadata & dependencies (uv-managed)
└── setup.py              # No-op shim kept for `python setup.py sdist`
```

## 🏛️ Standards Compliance

- **NIST SP 800-88 Rev 1** — U.S. Federal media sanitization guidelines (Clear/Purge)
- **IEEE 2883:2022** — Standard for sanitization of storage
- **DoD 5220.22-M** — 3-pass and 7-pass overwrite variants
- **ISO/IEC 27040** — Storage security guidelines

## ⚠️ Important Warnings

- **💀 DATA DESTRUCTION** — all data on the target device is permanently destroyed
- **🔒 ROOT REQUIRED** — must run with `sudo` for direct device access
- **💾 UNMOUNT FIRST** — unmount filesystems before wiping
- **🔌 STABLE POWER** — ensure uninterrupted power during operation
- **💿 RAID ARRAYS** — handle RAID configurations with extreme care

## 🛠️ Development

```bash
git clone https://github.com/41vi4p/BreakNWipe.git
cd BreakNWipe
uv sync             # installs deps + dev tools (pytest, black, flake8, mypy, isort)

make help          # All development commands
make lint          # uv run flake8 + mypy
make format        # uv run black + isort
make test          # uv run pytest with coverage

# Add/remove a dependency
uv add <package>
uv add --dev <package>
```

For the smart contract:

```bash
cd blockchain
pnpm install
npx hardhat test
```

Further reading: [docs/DESIGN.md](docs/DESIGN.md) · [docs/BLOCKCHAIN_INTEGRATION.md](docs/BLOCKCHAIN_INTEGRATION.md) · [docs/CHANGELOG.md](docs/CHANGELOG.md) · [SIH 2025 Presentation](docs/CodeBreakers_SIH25_PS1.pdf)

## 👥 Team CodeBreakers

| Member | Contribution |
|--------|-------------|
| **Blaise Rodrigues** (Team Lead) | Algorithms, Testing & Architecture Design |
| **David Porathur** | CLI Utility, Features Integration & Architecture Design |
| **Vanessa Rodrigues** | Next.js App, Research & Architecture Design |
| **Natasha Lewis** | UI & Research |
| **Chris Lopes** | Next.js App with digital signature verification |
| **Anastasia Lopes** | UI, Frontend & Research |

## 🌟 Impact

- **♻️ Reduce e-waste hoarding** by building user confidence in data destruction
- **🔄 Promote the circular economy** through safe device recycling and resource recovery (gold, copper, lithium, rare-earth metals)
- **🇮🇳 Support Digital India & Atmanirbhar Bharat** environmental goals
- **🏢 Enable secure ITAD** for financial services, healthcare, defense, and government
- **🤝 Create trust** in the recycling ecosystem — aligned with UN SDGs 9 & 13

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

```
BreakNWipe - Secure Data Wiping for Trustworthy IT Asset Recycling

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

---

<div align="center">

**🇮🇳 Made for India's e-waste solution | 🌍 Promoting the global circular economy**

**Developed with ❤️ by Team CodeBreakers — Smart India Hackathon 2025**

</div>
