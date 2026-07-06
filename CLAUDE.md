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
sudo uv run python -m breaknwipe.cli.main --gui           # FastAPI web GUI at :8000 (serves the built Next GUI)
sudo uv run python -m breaknwipe.cli.main --list-devices
uv run python -m breaknwipe.cli.main --help

# Web GUI development (Next.js). `--gui` serves the pre-built static bundle; for
# live GUI dev run the Next dev server against the FastAPI backend:
cd breaknwipe/breaknwipe-gui && npm install && npm run dev   # Next dev on :3000
sudo uv run python -m breaknwipe.cli.main --gui              # backend on :8000 (API is proxied automatically in dev)
cd breaknwipe/breaknwipe-gui && npm run build                # produce out/ (what --gui serves in production)

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

- **`breaknwipe/device/`** — hardware layer. `detector.py` identifies drive type and hidden areas (HPA/DCO via `hdparm`); `ata.py` and `nvme.py` issue hardware-level secure-erase/sanitize commands; `mobile.py` handles Android wiping via ADB/fastboot — its EDL (Qualcomm), SP Flash (MediaTek), and Odin (Samsung) modes are **intentionally unimplemented stubs** that return an error, not real code paths to "fix" without new tooling. `filesystem.py`/`health.py`/`fsck.py`/`partition.py` are the disk-utility-toolkit modules (the broader expansion beyond wipe-only) — deliberately kept isolated from the wipe-critical mount-detection code in `detector.py`/`handler.py`/`wipe_engine/engine.py` (those do *substring* matching against `mount` output, which over-matches harmlessly for wipe but would be a safety bug for these; `filesystem.py` always does exact `/proc/mounts` matching, reused by the others). `fsck.py`'s `FilesystemChecker` and `partition.py`'s `PartitionResizer` never auto-unmount, are **preview-first** (plan_* returns the exact commands without touching the disk), and gate destructive/offline operations behind mount-state + system-disk + typed-confirm checks — read their module docstrings for the full safety-gate order before touching them. `partition.py` covers grow (live/online for ext4/xfs/btrfs)/shrink/move + the LVM extend flow; all verified against loopback disks with data-integrity checks. `hexview.py` is the read-only raw-sector reader (`read_sectors`, O_RDONLY, 64 KiB-clamped) behind `GET /api/devices/{path}/sectors` and the GUI's `/hex` viewer — used to visually confirm a wipe zeroed a device. `recovery.py` is deleted-file recovery with two modes, both shelling out to forensic CLIs (chosen over the `pytsk3` C-binding for clean packaging): `scan_deleted`/`recover_files` use The Sleuth Kit (`fls`/`icat`) to undelete files **with their names** on NTFS/FAT/exFAT; `deep_scan_recover` uses PhotoRec (`photorec`) to signature-carve file bodies (no names) even when metadata is gone (ext4, quick-format). Scanning is read-only; recovery **refuses to write to the same device it's reading from** (would overwrite the data being recovered) — this is enforced in the module, not just the UI. Honest framing: a device fully wiped by a real algorithm has nothing to recover, and the UI says so. Behind `GET /api/recovery/available`, `POST /api/recovery/scan`, `POST /api/recovery/restore`, the GUI's `/recover` page, and the `breaknwipe recover` CLI command. Needs `sleuthkit` + `testdisk` system packages. `erasure_check.py` is the GUI's Verify pillar — confirms a *device* has actually been wiped (not certificate authenticity, see below), combining two read-only checks: `wipe_engine/verification.py`'s `WipeVerifier.verify_wipe_detailed()` (Shannon entropy, repeated-pattern, and known file-signature sampling of the raw device at quick/comprehensive/paranoid depth) with a best-effort recovery cross-check (`recovery.scan_deleted()` on any still-recognizable partition — no recognizable filesystem at all is itself treated as a good sign after a wipe, not a failure). Behind `POST /api/verify/erasure`, the GUI's `/verify` page, and `breaknwipe verify <device>`.
- **`breaknwipe/wipe_engine/`** — `algorithms.py` defines `AlgorithmType` (nist-clear/purge, dod-3pass/7pass, gutmann, random, zeros, custom) plus the REA family (`rea-basic`, `rea-multichain`, `rea-extreme`, `rea-fast`, `rea-custom`) as sequences of `WipePass`es; `engine.py` (`WipeEngine`) executes passes against a device path and reports progress via callback; `verification.py`'s `WipeVerifier` does read-back verification (entropy/pattern/file-signature sampling at quick/comprehensive/paranoid depth) — `verify_wipe()` (bool, used internally by `engine.py`'s post-wipe check) and `verify_wipe_detailed()` (full stats dict, used by `device/erasure_check.py` for the GUI's Verify pillar) share the same sampling logic. Its known-file-signature list must use real byte literals (`b'\x89PNG'`), not a doubled-backslash string (`b'\\x89PNG'`, 7 ASCII characters that never matches real binary data) — an earlier version had this bug and silently never detected any binary file signature; keep this in mind if touching that list again.
- **`breaknwipe/certificate/`** — `generator.py` (`CertificateGenerator`) produces the PDF (reportlab) + JSON report; `signature.py` handles RSA/X.509 digital signing; `qr.py` builds the verification QR (two formats: traditional and blockchain-enhanced, see `docs/BLOCKCHAIN_INTEGRATION.md`); `blockchain.py` (`BlockchainCertificateStore`) pushes the report hash/JSON to the Sepolia smart contract described below.
- **`breaknwipe/cli/`** — `main.py` is the click command group (`wipe`, `info`, `fsck`, `list-algorithms`, `batch`, `verify-certificate`, plus `--interactive`/`--gui`/`--list-devices` flags); `interactive.py` is the guided wizard; `expert.py` (`ExpertMode`) is the scriptable path used by direct flag invocations; `progress.py` renders Rich-based progress bars. `main()` is invoked with `prog_name='breaknwipe'` explicitly (see the `if __name__ == '__main__':` block) so Click's `_BREAKNWIPE_COMPLETE` shell-completion env var is honored regardless of invocation method (console-script entry point vs. `python -m` vs. the shell wrapper scripts generate) — shell completion (bash/zsh/fish) is Click's built-in mechanism, not hand-maintained; `complete_device_path()` is the one custom completer, for `/dev/sd*`/`/dev/nvme*` paths Click can't infer on its own.
- **`breaknwipe/web/`** — FastAPI server (`server.py`) exposing REST + WebSocket endpoints and serving the GUI; `session_manager.py` tracks in-progress wipe sessions; `recovery_manager.py` (`RecoverySessionManager`) mirrors it for deep-scan (PhotoRec) recovery jobs, which run in a background thread pool and stream progress over `WS /ws/recovery/{job_id}` (`POST /api/recovery/deep-scan/start` returns a `job_id` immediately; `GET /api/recovery/deep-scan/{job_id}` polls the same state for reconnects; `POST .../cancel` stops one early). This is what `--gui` launches. The disk-utility endpoints (`GET /api/devices/{path}/health`, `GET /api/devices/{path}/partitions`, `POST /api/fsck/check`, the partition-resize/LVM ones, `GET /api/devices/{path}/sectors`, and the recovery ones — `GET /api/recovery/available`, `POST /api/recovery/scan`, `POST /api/recovery/restore`, `POST /api/recovery/deep-scan/start`, `GET /api/recovery/deep-scan/{job_id}`, `POST /api/recovery/deep-scan/{job_id}/cancel`, `GET /api/recovery/view`) are defined as sync `def` handlers, not `async def` — FastAPI/Starlette runs those in a thread pool automatically, which matters since they call blocking `subprocess` code (`device/health.py`, `device/filesystem.py`, `device/fsck.py`, `device/recovery.py`). `fsck.py`'s safety gates apply identically here; there is no separate/weaker web-side check. `GET /api/recovery/view` (streams a recovered file's bytes for the GUI's browse/preview panel) only reads from folders a recovery operation actually wrote to during the server's lifetime (`WebServer.recovered_roots`, populated when a restore/deep-scan starts) — the client supplies a file path but never a root, so it can't become an arbitrary local file read, following the same `os.path.realpath` + prefix-check pattern as the existing `/api/download` allowlist. `POST /api/verify/erasure` (the GUI's Verify pillar — confirms a *device* was actually wiped clean, not certificate authenticity) calls `device/erasure_check.py`'s `check_erasure()`, which is read-only. `POST /api/verify/certificate` is a separate, GUI-unlinked endpoint: it accepts an uploaded `.json` wipe report (not a server-side path — the browser and server aren't guaranteed to share a filesystem view), writes it to a temp file, and calls `CertificateGenerator.verify_certificate()` (signature check) plus `verify_certificate_blockchain()` when the report carries a hash; kept as a working API surface in case a certificate-authenticity UI is wanted later. `server.py` mounts the built GUI (see `breaknwipe/breaknwipe-gui`) at `/` via `StaticFiles(html=True)` *after* registering the API routes (Starlette matches in registration order, so the `/` mount must come last or it would swallow `/api`); the old per-page HTML routes were removed, with a transitional fallback to `frontend_ui/` if the GUI isn't built.
- **`breaknwipe/breaknwipe-gui/`** — the web GUI: **Next.js 16 / React 19 / Tailwind v4 / TypeScript** (App Router), a Node subproject *inside* the Python package (analogous to `blockchain/`). It's a **static-export SPA** (`output: 'export'` in `next.config.ts` → an `out/` folder of client-rendered HTML/CSS/JS that fetches the REST/WebSocket API), so `sudo breaknwipe --gui` still launches one FastAPI server on one port — Node is a **build-time-only** dependency. Dev: `npm run dev` (Next :3000) + the FastAPI backend (:8000); `lib/api.ts` auto-detects the dev backend (port 3000 → :8000) vs. production same-origin, so no env file is needed. **Its `AGENTS.md` warns Next 16 differs from older Next — read `node_modules/next/dist/docs/` before writing GUI code.** Design system in `app/globals.css` (semantic light/dark tokens driven by a `data-theme` attribute + `prefers-color-scheme`, no-flash pre-paint script in `app/layout.tsx`); components in `components/`. Information architecture: `app/page.tsx` is a chrome-light landing page (hero + four color-coded pillar actions), not a device list; `components/app-shell.tsx` renders a horizontal top nav with those same four pillars as tabs (suppressed on `/`) plus Logs/Reports/About as compact tooltip icon buttons — the old sidebar-dashboard layout is gone. All four pillars — `/wipe`, `/recover`, `/verify` (device erasure check, not certificate authenticity), and `/utility` (device health/partitions/repair/hex — formerly the `/` device list) — show a shared `<DevicePicker>`/`<DeviceCard>` (in `components/`) when no `?path=` is given, so every pillar is a self-contained entry point. Part of a broader disk-toolkit roadmap in `docs/DISK_TOOLKIT_PLAN.md`.
- **`breaknwipe/logging/`** — local audit-trail persistence (`database.py`, `service.py`) independent of the blockchain anchor.
- **`blockchain/`** — a separate Hardhat/TypeScript project (its own `package.json`, not part of the Python package) containing the `ReportRegistryWithJson` Solidity contract deployed on Sepolia testnet. Three on-chain storage strategies of increasing cost: hash-only, JSON-via-event, full on-chain JSON. See `blockchain/README.md`.
- **`frontend_ui/`** — static HTML/CSS/JS served by the FastAPI web server (not a separate build step, no bundler).
- **datawipe webapp** (external, not in this repo) — a Next.js app at datawipe.vercel.app that scans certificate QR codes and cross-checks them against the Sepolia contract; this repo's blockchain integration is written to interoperate with it.

### Cross-cutting notes

- Both `breaknwipe/.env` and `blockchain/.env` are required for blockchain features and are gitignored; use the adjacent `.env.example` files as templates. Never hardcode RPC URLs, contract addresses, or private keys in source — `blockchain/hardhat.config.ts` reads `SEPOLIA_RPC_URL`/`PRIVATE_KEY` via `configVariable()` for this reason.
- Most device operations require root (`sudo`) for direct block-device access; the CLI checks this at startup (`check_root_privileges()` in `main.py`).
- `docs/BLOCKCHAIN_INTEGRATION.md` documents the QR payload schemas (traditional vs. blockchain-enhanced) — keep both in sync if you change `certificate/qr.py` or `certificate/generator.py`.
- Repo layout is intentional: `scripts/` (install/build/demo shell scripts + blockchain setup script), `docs/` (design docs, SIH presentation, changelog), `tests/` (standalone integration scripts, not pytest).
