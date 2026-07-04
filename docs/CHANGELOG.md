# Changelog

All notable changes to BreakNWipe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/). Every change to the codebase increments the version in `breaknwipe/__init__.py` and `pyproject.toml`.

## [2.6.1] - 2026-07-05

### Fixed
- **The `2.6.0` `.deb` was broken on install** — confirmed by real-world testing (thank you for catching this): `breaknwipe`/`sudo breaknwipe --interactive` failed with `Permission denied` / `No such file or directory` against `/opt/breaknwipe/src/.venv/bin/python`, and after a first fix attempt, `ModuleNotFoundError: No module named 'breaknwipe'`. Root cause: `uv sync` bakes *absolute* paths into the venv at sync time — the managed-Python interpreter symlink, and the project's own editable-install reference — and `scripts/build_packages.sh` was staging the build under `build/pkgroot/opt/breaknwipe/src`, a path that doesn't exist once installed at the real `/opt/breaknwipe/src`. `scripts/build_packages.sh` now builds directly at the real final absolute paths (`/opt/breaknwipe`, `/usr/bin`) inside the disposable build container instead of a separate staging tree, and forces `uv` to use its own managed Python (`--managed-python`) installed at that same fixed path (`UV_PYTHON_INSTALL_DIR=/opt/breaknwipe/python`), vendored into the package alongside `.venv`. Verified this time with a true cross-machine test: built in one throwaway container, then installed and run in a completely separate, unrelated one — `breaknwipe --help`/`--version`/`--list-devices` all work and the interpreter symlink resolves correctly.

## [2.6.0] - 2026-07-04

### Added
- Self-hosted APT repository, published to GitHub Pages: `sudo apt install breaknwipe` with real updates via `apt upgrade`, no re-running installer scripts
- `.github/workflows/apt-repo.yml` — builds the `.deb` and publishes a signed APT repo to the `gh-pages` branch on every `v*` tag push
- `docs/APT_REPO_SETUP_GUIDE.md` — one-time maintainer walkthrough (GPG key generation, GitHub secret, enabling Pages); deliberately manual since the private signing key is a supply-chain-critical secret
- README: APT install one-liner surfaced at the top and in the Installation/Uninstallation sections; "Repository Structure" and implemented-features list updated

### Changed
- `scripts/build_packages.sh` rewritten to build fully self-contained packages: BreakNWipe + all its Python dependencies are now vendored into a `uv`-managed virtual environment (same layout as `scripts/install.sh`) and wrapped with `fpm --input-type dir`, instead of fpm's `--input-type python` mechanism. That mechanism auto-detects install paths from whichever Python is active on the *build machine* — verified locally to silently bake in a broken, machine-specific path (a conda env's site-packages) when not built inside a clean container — and additionally requires `python3-packaging`/`python3-pip` just to run on modern Ubuntu/Debian (Python 3.12+ removed distutils from the stdlib). The new approach's only real runtime dependencies are the system tools BreakNWipe shells out to (`hdparm`, `nvme-cli`, `smartmontools`, `util-linux`), not Python packaging at all. Verified end-to-end in a clean Ubuntu 24.04 container: build → `apt-get install ./breaknwipe.deb` → `breaknwipe --help` all work.
- `scripts/build_packages.sh`: fixed a stale hardcoded `PACKAGE_VERSION="1.0.0"` (now read from `breaknwipe/__init__.py`), a wrong project `URL`, `--license "MIT"` (project is GPL-3.0-or-later), an RPM build that unconditionally aborted the whole script via `set -e` when `rpmbuild` wasn't installed (now skips gracefully, matching the existing AppImage pattern), a `create_repository_metadata`/`show_build_summary`/`create_checksums` bug where `find` recursed into its own `repository/` output and double-counted/corrupted-copied packages, and two `echo` calls missing `-e` that printed literal `\033[...]` escape codes instead of color
- `scripts/build_packages.sh` and `scripts/demo.sh`: fixed pervasive double-backslash (`\\`) line continuations that are invalid bash (should be single `\`) — multi-line `fpm`/`useradd`/`find -exec` commands were silently broken and, as far as could be determined, had never actually been executed successfully before

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
