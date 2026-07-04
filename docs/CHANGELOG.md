# Changelog

All notable changes to BreakNWipe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/). Every change to the codebase increments the version in `breaknwipe/__init__.py` and `pyproject.toml`.

## [2.5.5] - 2026-07-04

### Added
- Install/uninstall one-liners surfaced at the very top of `README.md` (right under the badges, before "About the Project"), linking down to the full `#installation`/`#uninstallation` sections for anyone who wants the commands without reading through the rest of the doc

## [2.5.4] - 2026-07-04

### Added
- `README.md` "Quick Links" nav bar above "About the Project", linking to the sections readers reach for most often (Features, How It Works, Quick Start, Blockchain Verification, Standards Compliance, Important Warnings, Development, License)

## [2.5.3] - 2026-07-04

### Added
- `README.md` "Uninstallation" section: `sudo make uninstall-system` for local checkouts, plus a download-and-run one-liner (`curl -fsSL .../scripts/uninstall.sh -o ... && sudo bash ...`) for hosts installed via `quickstart.sh` that no longer have a local clone — `uninstall.sh` only touches system paths, so it doesn't need the repo present. Documented as download-then-run rather than piped, since it prompts for interactive confirmation before removing data/dependencies.

## [2.5.2] - 2026-07-04

### Changed
- `README.md` now explicitly calls out that `quickstart.sh`/`install_dependencies.sh`/`install.sh`/`make install-system` require Ubuntu/Debian on x86_64 (they shell out to `apt`); `uv sync`/`pip install -e .` remain platform-agnostic but still need `hdparm`/`nvme-cli`/`smartmontools` provided separately on other distros

## [2.5.1] - 2026-07-04

### Added
- `scripts/quickstart.sh` — a curl-to-bash installer that clones the repository into a temp directory and hands off to `scripts/install.sh`, so a full system install needs no manual `git clone` first: `curl -fsSL .../scripts/quickstart.sh | sudo bash`

## [2.5.0] - 2026-07-04

### Added
- `scripts/install_dependencies.sh` — installs OS-level packages (`hdparm`, `nvme-cli`, `smartmontools`, `rsync`, build headers, etc.) and `uv` itself; Python dependencies are then installed with `uv sync`

### Changed
- `scripts/install.sh` (the system-wide installer used by `make install-system`) now copies the project source into `/opt/breaknwipe/src` and provisions its Python environment with `uv sync` instead of a hand-rolled `python3.10`/pip virtualenv; it delegates OS package installation to `scripts/install_dependencies.sh`
- Fixed a bug in the generated `breaknwipe` wrapper script where `$INSTALL_DIR` was never expanded (heredoc was fully quoted), so it resolved to a nonexistent `/venv/bin/python`; it now points at the correct `.venv` path
- `scripts/uninstall.sh` no longer purges a pip cache (irrelevant now that the project doesn't use pip)
- `Makefile`'s `install`, `install-system`, `run-interactive`, `run-list`, `run-help`, `test-device-detection`, and `security-check` targets now go through `uv sync` / `uv run`

### Removed
- `scripts/install_requirements.sh` and `requirements.txt` — superseded by `pyproject.toml` + `uv sync`
- `scripts/breaknwipe_wrapper.sh` — a dead, unreferenced file hardcoding a path from a contributor's local machine

## [2.4.3] - 2026-07-04

### Added
- `pyproject.toml` as the single source of truth for project metadata and dependencies, managed with [uv](https://docs.astral.sh/uv/); `uv.lock` committed for reproducible installs

### Changed
- `setup.py` reduced to a no-op `setup()` shim (metadata now lives in `pyproject.toml`); kept only so `python setup.py sdist`/`bdist_wheel` still work for `scripts/build_packages.sh`
- `Makefile`'s `dev-install`, `test`, `lint`, `format`, and `test-algorithms` targets now run through `uv sync` / `uv run` instead of bare `pip`/`pytest`/`flake8`/etc.

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
