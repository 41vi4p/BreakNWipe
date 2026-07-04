# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BreakNWipe is a secure data-wiping CLI/web utility built for Smart India Hackathon 2025 (Problem Statement SIH25070) by Team CodeBreakers. It wipes storage devices (HDD/SSD/NVMe/USB/Android) using standards-compliant algorithms, optionally layers a custom "Randomized Encryption Algorithm" (REA) cryptographic-erase step before overwriting, and produces a digitally signed, blockchain-anchored, QR-verifiable certificate of destruction. See `README.md` for the full feature list and problem statement context, and `docs/DESIGN.md` for the original architecture writeup.

## Versioning

**Every change in this repository must increment the version.** The version lives in two places and both must be updated together:
- `breaknwipe/__init__.py` → `__version__`
- `setup.py` → `version=`

Use semver: patch bump (`x.y.Z`) for fixes/docs/chores, minor bump (`x.Y.0`) for new features, major bump (`X.0.0`) for breaking changes. After bumping, add an entry to `docs/CHANGELOG.md` (Keep a Changelog format) and update the version badge in `README.md`.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run the CLI
sudo python -m breaknwipe.cli.main --interactive   # guided wizard
sudo python -m breaknwipe.cli.main --gui           # FastAPI web GUI at :8000
sudo python -m breaknwipe.cli.main --list-devices
python -m breaknwipe.cli.main --help

# Lint / format
make lint      # flake8 breaknwipe tests && mypy breaknwipe
make format    # black breaknwipe tests && isort breaknwipe tests

# Tests
# NOTE: no pytest unit-test suite currently exists (breaknwipe/tests/ is referenced
# by the Makefile but not present). `tests/` at repo root holds two standalone
# integration scripts, run directly:
python tests/test_blockchain_functionality.py
python tests/test_qr_consistency.py

# Package building / system install (see scripts/, all destructive — confirm with user)
make install-system     # scripts/install.sh + scripts/install_requirements.sh
make uninstall-system    # scripts/uninstall.sh
make package             # scripts/build_packages.sh (.deb/.rpm)
make demo                # scripts/demo.sh
```

Root console entry points (from `setup.py`): `breaknwipe` and `bwipe`, both mapping to `breaknwipe.cli.main:main`.

## Architecture

The package is organized as a pipeline: **device detection → algorithm selection → wipe execution → certification**, with two parallel front ends (CLI and web) driving the same engine.

- **`breaknwipe/device/`** — hardware layer. `detector.py` identifies drive type and hidden areas (HPA/DCO via `hdparm`); `ata.py` and `nvme.py` issue hardware-level secure-erase/sanitize commands; `mobile.py` handles Android wiping via ADB/fastboot — its EDL (Qualcomm), SP Flash (MediaTek), and Odin (Samsung) modes are **intentionally unimplemented stubs** that return an error, not real code paths to "fix" without new tooling.
- **`breaknwipe/wipe_engine/`** — `algorithms.py` defines `AlgorithmType` (nist-clear/purge, dod-3pass/7pass, gutmann, random, zeros, custom) plus the REA family (`rea-basic`, `rea-multichain`, `rea-extreme`, `rea-fast`, `rea-custom`) as sequences of `WipePass`es; `engine.py` (`WipeEngine`) executes passes against a device path and reports progress via callback; `verification.py` does read-back verification.
- **`breaknwipe/certificate/`** — `generator.py` (`CertificateGenerator`) produces the PDF (reportlab) + JSON report; `signature.py` handles RSA/X.509 digital signing; `qr.py` builds the verification QR (two formats: traditional and blockchain-enhanced, see `docs/BLOCKCHAIN_INTEGRATION.md`); `blockchain.py` (`BlockchainCertificateStore`) pushes the report hash/JSON to the Sepolia smart contract described below.
- **`breaknwipe/cli/`** — `main.py` is the click command group (`wipe`, `info`, `list-algorithms`, `batch`, `verify-certificate`, plus `--interactive`/`--gui`/`--list-devices` flags); `interactive.py` is the guided wizard; `expert.py` (`ExpertMode`) is the scriptable path used by direct flag invocations; `progress.py` renders Rich-based progress bars.
- **`breaknwipe/web/`** — FastAPI server (`server.py`) mounting `frontend_ui/` as static files and exposing REST + WebSocket endpoints; `session_manager.py` tracks in-progress wipe sessions; this is what `--gui` launches.
- **`breaknwipe/logging/`** — local audit-trail persistence (`database.py`, `service.py`) independent of the blockchain anchor.
- **`blockchain/`** — a separate Hardhat/TypeScript project (its own `package.json`, not part of the Python package) containing the `ReportRegistryWithJson` Solidity contract deployed on Sepolia testnet. Three on-chain storage strategies of increasing cost: hash-only, JSON-via-event, full on-chain JSON. See `blockchain/README.md`.
- **`frontend_ui/`** — static HTML/CSS/JS served by the FastAPI web server (not a separate build step, no bundler).
- **datawipe webapp** (external, not in this repo) — a Next.js app at datawipe.vercel.app that scans certificate QR codes and cross-checks them against the Sepolia contract; this repo's blockchain integration is written to interoperate with it.

### Cross-cutting notes

- Both `breaknwipe/.env` and `blockchain/.env` are required for blockchain features and are gitignored; use the adjacent `.env.example` files as templates. Never hardcode RPC URLs, contract addresses, or private keys in source — `blockchain/hardhat.config.ts` reads `SEPOLIA_RPC_URL`/`PRIVATE_KEY` via `configVariable()` for this reason.
- Most device operations require root (`sudo`) for direct block-device access; the CLI checks this at startup (`check_root_privileges()` in `main.py`).
- `docs/BLOCKCHAIN_INTEGRATION.md` documents the QR payload schemas (traditional vs. blockchain-enhanced) — keep both in sync if you change `certificate/qr.py` or `certificate/generator.py`.
- Repo layout is intentional: `scripts/` (install/build/demo shell scripts + blockchain setup script), `docs/` (design docs, SIH presentation, changelog), `tests/` (standalone integration scripts, not pytest).
