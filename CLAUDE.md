# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BreakNWipe is a secure data-wiping CLI/web utility built for Smart India Hackathon 2025 (Problem Statement SIH25070) by Team CodeBreakers. It wipes storage devices (HDD/SSD/NVMe/USB/Android) using standards-compliant algorithms, optionally layers a custom "Randomized Encryption Algorithm" (REA) cryptographic-erase step before overwriting, and produces a digitally signed, blockchain-anchored, QR-verifiable certificate of destruction. See `README.md` for the full feature list and problem statement context, and `docs/DESIGN.md` for the original architecture writeup.

## Versioning

**Every change in this repository must increment the version.** The version lives in two places and both must be updated together:
- `breaknwipe/__init__.py` → `__version__`
- `pyproject.toml` → `version =`

(`setup.py` is a no-op shim retained only so `python setup.py sdist`/`bdist_wheel` keep working for `scripts/build_packages.sh`; it has no version of its own — all metadata lives in `pyproject.toml`.)

Use semver: patch bump (`x.y.Z`) for fixes/docs/chores, minor bump (`x.Y.0`) for new features, major bump (`X.0.0`) for breaking changes. After bumping, add an entry to `docs/CHANGELOG.md` (Keep a Changelog format) and update the version badge in `README.md`.

## Commands

Dependencies and the dev environment are managed with [uv](https://docs.astral.sh/uv/); `pyproject.toml` is the single source of truth for metadata and dependencies (`uv.lock` pins exact versions and is committed). There is no `requirements.txt` — add dependencies with `uv add <pkg>` (`uv add --dev <pkg>` for dev-only tools) and re-run `uv sync`. `setup.py` is a version-less no-op shim kept only so `python setup.py sdist`/`bdist_wheel` still work for `scripts/build_packages.sh`.

```bash
# Install for development (creates .venv, installs deps + dev group from pyproject.toml)
uv sync

# Add / remove a dependency (updates pyproject.toml + uv.lock)
uv add <package>
uv add --dev <package>       # dev-only tool (pytest, black, etc.)
uv remove <package>

# Run the CLI (uv run resolves the project's .venv automatically)
sudo uv run python -m breaknwipe.cli.main --interactive   # guided wizard
sudo uv run python -m breaknwipe.cli.main --gui           # FastAPI web GUI at :8000
sudo uv run python -m breaknwipe.cli.main --list-devices
uv run python -m breaknwipe.cli.main --help

# Lint / format
make lint      # uv run flake8 breaknwipe tests && uv run mypy breaknwipe
make format    # uv run black breaknwipe tests && uv run isort breaknwipe tests

# Tests
# NOTE: no pytest unit-test suite currently exists (breaknwipe/tests/ is referenced
# by the Makefile but not present). `tests/` at repo root holds two standalone
# integration scripts, run directly:
uv run python tests/test_blockchain_functionality.py
uv run python tests/test_qr_consistency.py

# System-level (non-Python) dependencies only: hdparm, nvme-cli, smartmontools, uv itself
sudo ./scripts/install_dependencies.sh

# Package building / system install (see scripts/, all destructive — confirm with user)
# install.sh provisions a dedicated system user + systemd service and manages its
# own copy of the source at /opt/breaknwipe/src with `uv sync` (it calls
# install_dependencies.sh internally, so running it standalone first is optional).
make install-system     # scripts/install.sh
make uninstall-system    # scripts/uninstall.sh
# scripts/quickstart.sh: curl-to-bash entry point that clones the repo to a
# temp dir and hands off to install.sh, for installing without a local checkout
make package             # scripts/build_packages.sh (.deb/.rpm)
make demo                # scripts/demo.sh
```

`scripts/build_packages.sh` builds self-contained packages: it vendors BreakNWipe + all Python
deps into a `uv`-managed venv (same layout as `install.sh`), then wraps that directory tree with
`fpm --input-type dir`. It deliberately does NOT use fpm's `--input-type python` — that mechanism
auto-detects install paths from whichever Python is active on the *build machine* (verified to
silently bake in a broken, machine-specific path, e.g. a conda env's site-packages, if built
outside a clean container) and needs extra packages (`python3-packaging`, `python3-pip`) to even
run on modern Ubuntu/Debian since distutils was removed from the stdlib in Python 3.12. Always
build inside a pinned container (`docker run ... ubuntu:24.04 bash scripts/build_packages.sh`),
never on a bare dev machine, for a build that's actually portable.

`.github/workflows/apt-repo.yml` builds that `.deb` (inside the same pinned container) and
publishes a signed APT repository to the `gh-pages` branch on every `v*` tag push, so
`sudo apt install breaknwipe` works from `https://41vi4p.github.io/BreakNWipe/apt`. One-time
maintainer setup (GPG key generation, GitHub secret, enabling Pages) is a manual walkthrough in
`docs/APT_REPO_SETUP_GUIDE.md` — deliberately not automated, since the private signing key is a
supply-chain-critical secret that shouldn't be generated or handled by an agent.

Root console entry points (from `pyproject.toml`'s `[project.scripts]`): `breaknwipe` and `bwipe`, both mapping to `breaknwipe.cli.main:main`.

## Architecture

The package is organized as a pipeline: **device detection → algorithm selection → wipe execution → certification**, with two parallel front ends (CLI and web) driving the same engine.

- **`breaknwipe/device/`** — hardware layer. `detector.py` identifies drive type and hidden areas (HPA/DCO via `hdparm`); `ata.py` and `nvme.py` issue hardware-level secure-erase/sanitize commands; `mobile.py` handles Android wiping via ADB/fastboot — its EDL (Qualcomm), SP Flash (MediaTek), and Odin (Samsung) modes are **intentionally unimplemented stubs** that return an error, not real code paths to "fix" without new tooling. `filesystem.py`/`health.py`/`fsck.py` are the disk-utility-toolkit modules (Phase 1a of a broader expansion beyond wipe-only) — deliberately kept isolated from the wipe-critical mount-detection code in `detector.py`/`handler.py`/`wipe_engine/engine.py` (those do *substring* matching against `mount` output, which over-matches harmlessly for wipe but would be a safety bug for fsck; `filesystem.py` always does exact `/proc/mounts` matching instead). `fsck.py`'s `FilesystemChecker` never auto-unmounts and refuses `--repair` outright on anything mounted — see its module docstring for the full safety-gate order before touching it.
- **`breaknwipe/wipe_engine/`** — `algorithms.py` defines `AlgorithmType` (nist-clear/purge, dod-3pass/7pass, gutmann, random, zeros, custom) plus the REA family (`rea-basic`, `rea-multichain`, `rea-extreme`, `rea-fast`, `rea-custom`) as sequences of `WipePass`es; `engine.py` (`WipeEngine`) executes passes against a device path and reports progress via callback; `verification.py` does read-back verification.
- **`breaknwipe/certificate/`** — `generator.py` (`CertificateGenerator`) produces the PDF (reportlab) + JSON report; `signature.py` handles RSA/X.509 digital signing; `qr.py` builds the verification QR (two formats: traditional and blockchain-enhanced, see `docs/BLOCKCHAIN_INTEGRATION.md`); `blockchain.py` (`BlockchainCertificateStore`) pushes the report hash/JSON to the Sepolia smart contract described below.
- **`breaknwipe/cli/`** — `main.py` is the click command group (`wipe`, `info`, `fsck`, `list-algorithms`, `batch`, `verify-certificate`, plus `--interactive`/`--gui`/`--list-devices` flags); `interactive.py` is the guided wizard; `expert.py` (`ExpertMode`) is the scriptable path used by direct flag invocations; `progress.py` renders Rich-based progress bars. `main()` is invoked with `prog_name='breaknwipe'` explicitly (see the `if __name__ == '__main__':` block) so Click's `_BREAKNWIPE_COMPLETE` shell-completion env var is honored regardless of invocation method (console-script entry point vs. `python -m` vs. the shell wrapper scripts generate) — shell completion (bash/zsh/fish) is Click's built-in mechanism, not hand-maintained; `complete_device_path()` is the one custom completer, for `/dev/sd*`/`/dev/nvme*` paths Click can't infer on its own.
- **`breaknwipe/web/`** — FastAPI server (`server.py`) mounting `frontend_ui/` as static files and exposing REST + WebSocket endpoints; `session_manager.py` tracks in-progress wipe sessions; this is what `--gui` launches. The disk-utility endpoints (`GET /api/devices/{path}/health`, `GET /api/devices/{path}/partitions`, `POST /api/fsck/check`) are defined as sync `def` handlers, not `async def` — FastAPI/Starlette runs those in a thread pool automatically, which matters since they call blocking `subprocess` code (`device/health.py`, `device/filesystem.py`, `device/fsck.py`). `fsck.py`'s safety gates apply identically here; there is no separate/weaker web-side check.
- **`breaknwipe/logging/`** — local audit-trail persistence (`database.py`, `service.py`) independent of the blockchain anchor.
- **`blockchain/`** — a separate Hardhat/TypeScript project (its own `package.json`, not part of the Python package) containing the `ReportRegistryWithJson` Solidity contract deployed on Sepolia testnet. Three on-chain storage strategies of increasing cost: hash-only, JSON-via-event, full on-chain JSON. See `blockchain/README.md`.
- **`frontend_ui/`** — static HTML/CSS/JS served by the FastAPI web server (not a separate build step, no bundler).
- **datawipe webapp** (external, not in this repo) — a Next.js app at datawipe.vercel.app that scans certificate QR codes and cross-checks them against the Sepolia contract; this repo's blockchain integration is written to interoperate with it.

### Cross-cutting notes

- Both `breaknwipe/.env` and `blockchain/.env` are required for blockchain features and are gitignored; use the adjacent `.env.example` files as templates. Never hardcode RPC URLs, contract addresses, or private keys in source — `blockchain/hardhat.config.ts` reads `SEPOLIA_RPC_URL`/`PRIVATE_KEY` via `configVariable()` for this reason.
- Most device operations require root (`sudo`) for direct block-device access; the CLI checks this at startup (`check_root_privileges()` in `main.py`).
- `docs/BLOCKCHAIN_INTEGRATION.md` documents the QR payload schemas (traditional vs. blockchain-enhanced) — keep both in sync if you change `certificate/qr.py` or `certificate/generator.py`.
- Repo layout is intentional: `scripts/` (install/build/demo shell scripts + blockchain setup script), `docs/` (design docs, SIH presentation, changelog), `tests/` (standalone integration scripts, not pytest).
