# Changelog

All notable changes to BreakNWipe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/). Every change to the codebase increments the version in `breaknwipe/__init__.py` and `setup.py`.

## [2.4.2] - 2026-07-04

### Added
- `CLAUDE.md` with architecture notes and a versioning policy for future development sessions
- This changelog

## [2.4.1] - 2026-07-04

### Added
- GNU GPLv3 `LICENSE`
- `.env.example` templates for `breaknwipe/` and `blockchain/`
- Badges, Smart India Hackathon 2025 context, and an implemented-vs-planned feature checklist in `README.md`
- Real documentation for the `ReportRegistryWithJson` smart contract in `blockchain/README.md` (replacing the stock Hardhat sample readme)

### Changed
- Reorganized the repository: design docs and the SIH presentation moved to `docs/`, install/build/demo scripts moved to `scripts/`, integration test scripts moved to `tests/`
- Updated the `Makefile` and inter-script references for the new paths
- `setup.py` license switched from MIT to `GPL-3.0-or-later`; repository URLs corrected to `github.com/41vi4p/BreakNWipe`
- `hardhat.config.ts` now reads `SEPOLIA_RPC_URL` / `PRIVATE_KEY` via Hardhat config variables instead of hardcoding them

### Removed
- Committed secrets: `breaknwipe/.env`, `blockchain/.env`, and hardcoded RPC URLs/private keys in `hardhat.config.ts`, `blockchain_config.json`, and a test script
- Tracked `breaknwipe.egg-info/` and `__pycache__/` build artifacts

### Security
- Purged the leaked Infura project ID and wallet private keys from the entire git history using `git filter-repo`, then force-pushed the rewritten history

## [1.0.0] – [2.1.2] - 2025

Initial Smart India Hackathon 2025 submission and early iterations: core wipe engine (NIST/DoD/Gutmann algorithms), device detection (HDD/SSD/NVMe/HPA-DCO), PDF/JSON certificate generation with digital signatures and QR codes, interactive and expert CLI modes, FastAPI web GUI, Android ADB wiping, and blockchain anchoring via the `ReportRegistryWithJson` Sepolia contract with datawipe webapp verification.
