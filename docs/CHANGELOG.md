# Changelog

All notable changes to BreakNWipe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/). Every change to the codebase increments the version in `breaknwipe/__init__.py` and `pyproject.toml`.

## [3.3.0] - 2026-07-06

Phase 4 (final) of the disk-toolkit roadmap: **deleted-file recovery.**

### Added
- **Deleted-file recovery** — a new `breaknwipe/device/recovery.py` with two complementary modes,
  both shelling out to established forensic tools (matching the project's lsblk/hdparm/blkid
  pattern):
  - *Quick scan (by name)* via **The Sleuth Kit** (`fls` to enumerate deleted entries, `icat` to
    extract them by metadata address) — recovers files **with their original names** on NTFS / FAT /
    exFAT, the common "I deleted files off my USB stick / SD card / Windows drive" case.
  - *Deep scan (by content)* via **PhotoRec** (`photorec`, signature-based carving) — recovers file
    *bodies* even when filesystem metadata is gone (ext4, quick-formatted, or damaged drives), at the
    cost of losing original filenames.
- **Honest framing throughout:** the UI states plainly that a drive securely wiped by BreakNWipe has
  nothing to recover — recovery is for accidents, not for undoing a wipe.
- **Safety:** scanning is read-only; recovery only writes to a caller-chosen output folder and
  **refuses if that folder is on the same device being recovered from** (which would overwrite the
  very data being recovered), enforced in the module (not just the UI). Validated block-device paths
  throughout.
- **Endpoints** (sync `def` → Starlette thread pool, like fsck/resize): `GET /api/recovery/available`
  (which tools are installed), `POST /api/recovery/scan` (list recoverable files), `POST
  /api/recovery/restore` (extract selected inodes, or deep-carve).
- **GUI** — a new `/recover` page: pick a partition, choose Quick or Deep scan, browse the deleted
  files (name / size / path) with select-all and per-file checkboxes, set an output folder, and
  recover. Reachable from each device page ("Recover files").
- **CLI** — a new `breaknwipe recover <partition>` command (scan-only by default; `--output` +
  `--all` to restore, `--deep` for PhotoRec carving).
- **Packaging** — `sleuthkit` and `testdisk` added to `scripts/install_dependencies.sh` and the
  `.deb`/`.rpm` `--depends`.

## [3.2.1] - 2026-07-06

### Fixed
- **Hex viewer now scrolls through the whole device.** The initial version showed only a fixed
  window with Prev/Next buttons; it's been rebuilt as a proper **virtualized scroller** (like
  Autopsy) — one continuous scroll pane over the entire device, with only the visible rows rendered
  and their backing 8 KiB chunks fetched lazily as they scroll into view (so even a multi-TB drive
  scrolls smoothly). Jump-to-offset, Start/End, and 512-byte sector-boundary highlighting are kept;
  not-yet-loaded bytes show as `··` until their chunk arrives.

## [3.2.0] - 2026-07-06

Phase 3 of the disk-toolkit roadmap: **hex / sector viewer.**

### Added
- **Raw sector viewer** — a new read-only `breaknwipe/device/hexview.py` (`read_sectors(path,
  offset, length)`) opens a device with `O_RDONLY`, seeks, and reads a **bounded** chunk (clamped to
  64 KiB) returned base64-encoded alongside the device's total size. Validated block-device paths;
  reading raw devices requires root. New endpoint `GET /api/devices/{path}/sectors?offset=&length=`.
- **Hex viewer GUI** — a new `/hex` page and `HexViewer` component: hex + ASCII columns with an
  offset gutter, **512-byte sector boundaries marked**, jump-to-offset (hex `0x…` or decimal), and
  windowed paging (only the visible window is fetched/rendered, so multi-TB devices are fine).
  Reachable from each device page ("View sectors") and — the point of it — from the **post-wipe
  completion screen**, so you can immediately open the drive and *see* it's zeroed.
- Verified on a loopback device: wrote a known pattern and read it back byte-exact through both the
  function and the HTTP endpoint; confirmed reads past the data return zeros; confirmed the 64 KiB
  length clamp and invalid-path refusal; and confirmed that after zeroing the device the viewer
  reads all zeros — the wipe-verification use case.

## [3.1.1] - 2026-07-06

### Fixed / Added (GUI)
- **Resumable wipe progress** — starting a wipe and then navigating away no longer loses access to
  the running operation. The wipe page now reconnects to an in-progress (or the most recent) wipe
  for the device on load (via `/api/wipe/sessions` + the WebSocket, which already reports current
  status on connect), and the Devices page shows a "wipe in progress · Resume →" banner for any
  active wipe.
- **Cancel a running wipe** — a Cancel button on the progress view (wired to the existing
  `/api/wipe/cancel/{id}` endpoint), plus a "Start another wipe" action once a wipe finishes.
- **Richer About page** — full project overview, a capabilities grid, Team CodeBreakers with roles,
  a GitHub link, and the live system-info panel.

## [3.1.0] - 2026-07-06

Phase 2 of the disk-toolkit roadmap: **partition management with full resize.**

### Added
- **Partition resize** — new isolated `breaknwipe/device/partition.py` (same safety discipline as
  `fsck.py`), shelling out to `growpart`/`sfdisk`/`resize2fs`/`ntfsresize`/`xfs_growfs`/`btrfs`/
  `pvresize`/`lvextend`:
  - **Grow** a partition into adjacent free space and grow its filesystem — **live/online** for
    ext4/XFS/Btrfs, which is what makes extending a root partition possible without a live USB. This
    is the fix for the common "my VM/root disk grew but the partition didn't expand" case. LVM is
    handled too (grow the PV, then `lvextend -r` the logical volume).
  - **Shrink** (filesystem-first, then the partition table) — offline only; XFS is honestly reported
    as un-shrinkable; refuses when mounted.
  - **Move** (block-copy + partition-table rewrite) — experimental and gated hardest: offline only,
    non-overlapping relocations only (an interrupted overlapping copy is unrecoverable), explicit
    force + typed confirmation.
  - Every operation is **preview-first**: the exact shell commands are computed and shown before
    anything runs. Never auto-unmounts; system-disk operations require force.
- **Disk-layout inspection** (`get_disk_layout`) — partitions + free-space gaps + GPT/MBR table type
  + LVM detection, via `sfdisk --json` + `lsblk`.
- **Web GUI**: an interactive proportional **partition map** on each device's page (partitions +
  free space), with per-partition Extend/Shrink/Move actions that preview the exact commands and
  require typed confirmation. New endpoints `GET /api/devices/{path}/partition-table`,
  `POST /api/partition/resize` (dry-run plan + apply), `POST /api/lvm/extend`.
- **CLI**: `breaknwipe resize <partition> --mode grow|shrink|move [--size|--start] [--apply] [--force]`
  — previews by default, `--apply` to execute.
- Packaging: `cloud-guest-utils`, `lvm2`, `xfsprogs`, `btrfs-progs`, `ntfs-3g` added to
  `scripts/install_dependencies.sh` and the `.deb`/`.rpm` dependencies.
- Verified end-to-end on disposable loopback disks (not just review): live grow of a mounted ext4
  partition (~19MB→~103MB) with byte-identical file integrity; offline shrink (120→60MB) with
  integrity; non-overlapping move to a new offset with integrity; and every safety refusal
  (mounted-shrink, overlapping-move, over-size-shrink, whole-disk) firing correctly.

## [3.0.0] - 2026-07-06

Repositioning release: BreakNWipe is now a **complete, approachable disk toolkit**, not just a
secure-wipe utility — with a brand-new GUI. Secure wipe + tamper-proof certificates remain a
flagship feature. The CLI and wipe engine are unchanged and fully compatible. This is Phase 1 of a
larger roadmap (see `docs/DISK_TOOLKIT_PLAN.md`); partition resize, a sector/hex viewer, and file
recovery follow in subsequent releases.

### Added
- **Brand-new web GUI** built with Next.js 16 / React 19 / Tailwind v4 / TypeScript, living at
  `breaknwipe/breaknwipe-gui/` (a Node subproject inside the package). It replaces the old
  hand-written static HTML pages with a professional, component-based interface featuring a real
  design system, **light and dark themes** (a `data-theme` toggle with a `prefers-color-scheme`
  fallback and a no-flash pre-paint script), and a consistent "control console" identity
  (monospace for all technical data — device paths, sizes, sectors).
- The GUI re-implements every existing feature (device list, drive health/lifespan, partitions,
  filesystem check/repair, secure wipe with live WebSocket progress and certificate download, audit
  log, certificates, about) against the unchanged backend API.

### Changed
- **Delivery model:** the GUI is built as a static export (`output: 'export'`) and served by the
  existing FastAPI backend, so `sudo breaknwipe --gui` still launches a single server on a single
  port. `web/server.py` now mounts the built bundle at `/` (`breaknwipe/breaknwipe-gui/out`,
  located relative to the package) and its old per-page HTML routes were removed; `/api/*` and
  `/ws/*` are unchanged. A transitional fallback to the legacy `frontend_ui/` remains if the GUI
  hasn't been built.
- **Packaging:** `scripts/build_packages.sh` and `scripts/install.sh` now build the GUI (`npm ci &&
  npm run build`) before vendoring the source, then strip `node_modules`/`.next` so only the static
  `out/` bundle ships. Node.js 20 is a **build-time-only** dependency (added to
  `scripts/install_dependencies.sh` and the build container via NodeSource); runtime is still just
  the Python venv. Verified end-to-end with a true cross-machine test: `.deb` built with the GUI in
  one clean container, installed in a separate one, and confirmed the GUI is served (routes 200,
  assets 200, `/api/*` still resolves under the mount, unknown paths 404).

## [2.8.2] - 2026-07-05

### Fixed
- Remaining pre-existing CodeQL alerts, all now resolved:
  - **`py/command-line-injection` (5 alerts, `device/detector.py`)**: `_probe_device()` — the single choke point feeding `_update_from_lsblk`/`_update_from_hdparm`/`_update_from_smartctl`/`_update_from_nvme`'s `subprocess.run` calls — now validates the caller-supplied `device_path` via the same `validate_block_device_path()` introduced for `fsck.py` in 2.8.1. `list_devices()`'s internal call path already only ever passes real, existing device paths, so this is a no-op there; it matters for `get_device_info()`, which takes a path directly from the CLI or a web request.
  - **`py/path-injection` (2 alerts, `web/server.py`'s `/api/download` endpoint)**: the existing `allowed_dirs` check compared the *raw, unresolved* `file_path` string against allowed directory prefixes — a traversal sequence (`/home/../../etc/passwd`) passed the naive `startswith('/home')` check while actually resolving outside every allowed directory. Now resolves both the requested path and the allowed directories with `os.path.realpath()` before comparing, and anchors the prefix check on `os.sep` so an allowed dir of `/home` can no longer match an unrelated sibling like `/homefoo`.
  - **`py/stack-trace-exposure` (1 alert, `/api/system-info`, plus the `/api/download` handler while it was already being touched for the path-injection fix)**: raw exception text no longer flows into the HTTP response; real errors are logged server-side via `logger.exception(...)` and the client gets a generic message.
- **Follow-on fix surfaced by the `detector.py` validation above**: `cli/main.py`'s `info` command and `cli/expert.py`'s `run_wipe` both called `.model`/`.capacity_bytes` etc. on the result of `get_device_info()` without checking for `None` first. Previously an implausible-looking device path would still make it through `_probe_device()` as an mostly-empty-but-non-`None` object (each `_update_from_*` method silently swallowed its own subprocess failure), so this never actually surfaced; now that invalid paths correctly return `None`, both call sites needed an explicit `None` check to avoid a confusing `AttributeError` instead of a clear error message. In `expert.py` this was a real latent bug: with `--force` set, the code didn't return on this failure at all and would have crashed later trying to read `device_info.capacity_bytes` for an actual (non-dry-run) wipe.
- All fixes verified end-to-end against a live server and real (disposable) devices, not just review: confirmed `/etc/passwd` and similar non-device paths are cleanly refused everywhere (CLI `info`, CLI `wipe --force --dry-run`, the web health endpoint) without any crash; confirmed a raw path-traversal request (tested with `curl --path-as-is` specifically because plain `curl` normalizes `../` client-side and would have made the test meaningless) is correctly blocked with 403 while a legitimate download still returns 200; confirmed the "prefix without separator" fix directly (`/homefoo/secret.txt` no longer matches an allowed `/home` prefix).

## [2.8.1] - 2026-07-05

### Fixed
- **CodeQL alert `py/command-line-injection` in `device/fsck.py`** (and the same pattern in `device/filesystem.py`'s `get_filesystem_type`/`list_partitions`): user-supplied partition/device paths (from the CLI argument or the web `/api/fsck/check` request body) now go through a new `validate_block_device_path()` check before being passed to `subprocess.run`. `subprocess.run` here was never called with `shell=True`, so shell-metacharacter injection (`;`, `|`, backticks) was never actually exploitable — but an unvalidated string starting with `-` could still be misread as a flag by the invoked tool (CWE-88 argument injection), and validation gives a much clearer refusal than a raw tool error either way. The new check requires the path to both look like a device path (`/dev/...`) and resolve to a real, existing block device (`os.stat` + `S_ISBLK`) — closing off the injection vector entirely, not just filtering characters. Verified with real malicious inputs (`--repair-force`, `/etc/passwd`, `; rm -rf / #`, `$(whoami)`, path traversal) against a live server and the CLI: all cleanly refused before any subprocess runs, with normal device paths unaffected.
- **CodeQL alert `py/stack-trace-exposure` in the new web `/api/fsck/check`, `/api/devices/{path}/health`, and `/api/devices/{path}/partitions` endpoints**: unexpected errors no longer include the raw exception string in the HTTP response (`detail=f"...: {e}"`) — the real error is now logged server-side (`logger.exception(...)`) and the client gets a generic message instead.

Five further pre-existing CodeQL alerts (command-line-injection in `device/detector.py`'s `_update_from_lsblk`/`_update_from_hdparm`/`_update_from_smartctl`/`_update_from_nvme`, predating this session's work) and three more (path-injection/stack-trace-exposure in the pre-existing `/api/download` and `/api/system-info` endpoints) were identified but intentionally left untouched pending a separate decision, since they sit in the wipe-critical device-detection path this project has otherwise been careful to keep isolated from newer, more experimental code.

## [2.8.0] - 2026-07-05

### Added
- **Web GUI now surfaces the drive health dashboard and filesystem repair** (Phase 2 of the disk-utility toolkit, following the CLI-only Phase 1a/1b): a new "Details / Health / Repair" button on each device card opens `device-detail.html`, showing device info, SMART health/lifespan, a partitions table, and a check/repair panel for `fsck`.
- New endpoints: `GET /api/devices/{path}/health`, `GET /api/devices/{path}/partitions`, `POST /api/fsck/check` — all defined as sync (not async) route handlers so FastAPI/Starlette runs their blocking `subprocess` calls in a thread pool rather than blocking the event loop. Every fsck safety gate (never auto-unmounts, refuses `--repair` on a mounted partition, requires `force` for system-disk/btrfs repair) applies identically to the web layer, since it calls the exact same `FilesystemChecker` the CLI uses — there is no separate, potentially-weaker path for the web UI.
- `web/models.py`'s `DeviceInfo` widened to include `mount_points`/`is_system_disk`, fixing a pre-existing gap where `session_manager.py` silently dropped both fields even though `StorageDevice.to_dict()` already carried them.
- Verified end-to-end against a live server (not just code review): started the real FastAPI server against a real loopback ext4 filesystem and confirmed `/api/devices`, `/device-detail.html`, the new health/partitions endpoints, and `/api/fsck/check` all work over real HTTP — including confirming `--repair` on a mounted partition is refused through the API exactly as it is through the CLI.

## [2.7.1] - 2026-07-05

### Added
- **Shell tab-completion** for the CLI (bash/zsh/fish), generated dynamically from the actual Click command tree via Click's built-in shell-completion support — so it's never hand-maintained and can't drift out of sync with the real commands/options. A custom completer (`complete_device_path`) suggests real `/dev/sd*`/`/dev/nvme*` paths for `wipe --device`, `info <device>`, and `fsck <partition>`; everything else (subcommands, `--algorithm`/Choice options, `--output` paths) is completed automatically by Click. `sudo apt install breaknwipe` and `scripts/install.sh`/`make install-system` set this up automatically (when `bash-completion` is installed); manual bash/zsh/fish setup for `uv sync`/pip installs is documented in the README.
- `cli/main.py`'s `main()` now pins `prog_name='breaknwipe'` explicitly — without it, Click derives the shell-completion env var name from `sys.argv[0]`, which for `python -m breaknwipe.cli.main` invocation is the resolved module file path, silently breaking `_BREAKNWIPE_COMPLETE` (confirmed: completion mode didn't activate at all before this fix, it just ran the CLI normally).

### Fixed
- `scripts/install.sh`'s bash-completion setup previously wrote unconditionally to `/etc/bash_completion.d/breaknwipe`, which would abort the *entire* install script (via `set -e`) on any system where that directory doesn't already exist (common on minimal installs — confirmed via testing) — now checks for the bash-completion infrastructure first and creates the directory as needed, matching how other Debian packages handle this legacy compat directory.
- The old bash completion script (hand-maintained, static, install.sh-only) has been replaced — it was already stale (missing the new `fsck` command entirely) and only ever covered users who ran the full `install.sh` system installer. The `.deb` package's `postinst` now sets up completion too.

## [2.7.0] - 2026-07-05

### Added
- **Drive health & partition dashboard** (Phase 1a of a broader disk-utility toolkit, alongside secure wiping): `breaknwipe info <device>` now shows vendor/firmware/WWN, mount status, a health summary (SMART overall status, temperature, power-on hours, and — where a reliable source exists — an estimated remaining-lifespan percentage), and a partitions table (path, size, filesystem type, mount point). New modules `breaknwipe/device/filesystem.py` (partition listing, filesystem-type detection via `blkid`, exact mount-point detection via `/proc/mounts`) and `breaknwipe/device/health.py` (SMART/lifespan snapshot, reusing NVMe's existing `percentage_used` parsing and adding SATA/USB SMART wear-attribute parsing). Lifespan is deliberately only reported when a standardized/reliable source exists (NVMe's spec-mandated wear indicator, or a recognized SATA SSD wear attribute) — HDDs and unrecognized SSDs show raw health indicators instead of a fabricated number.
- **Filesystem repair**: new `breaknwipe fsck <partition> [--repair] [--force] [--filesystem TYPE]` command. Check-only (no `--repair`) is the default and never modifies anything; dispatches to the right tool per filesystem type (`e2fsck`, `fsck.fat`, `fsck.exfat`, `ntfsfix`, `xfs_repair`, `btrfs check`). New `breaknwipe/device/fsck.py` implements the safety model: refuses on non-filesystem block types (swap/LUKS/LVM/RAID members) and whole disks with no filesystem; **never auto-unmounts** and refuses `--repair` outright on a mounted partition (unlike the wipe path, force-unmounting something you intend to keep risks corrupting in-flight writes); requires `--force` to repair a system-mounted-type partition or a btrfs filesystem (upstream discourages `btrfs check --repair` except when necessary); correctly interprets the standard fsck(8) exit-code bitmask (e.g. exit code 1 = "errors corrected" is a *success*, not a failure — a naive zero-check would misreport it).
- Both features verified against real, disposable loopback filesystems (not just code review): confirmed correct filesystem-type/mount detection, confirmed `--repair` correctly refuses on a mounted filesystem, and confirmed the exit-code-bitmask interpretation against an intentionally-corrupted ext4 filesystem (check-only correctly reports the errors as uncorrected; `--repair` correctly fixes them and reports success despite a nonzero exit code).

### Fixed
- `breaknwipe/device/filesystem.py`'s partition listing now falls back to `blkid` when `lsblk`'s own `FSTYPE` column comes back empty (observed with standalone loop devices carrying a real filesystem) — the same robustness `get_filesystem_type()` already had.

## [2.6.2] - 2026-07-05

### Changed
- `.github/workflows/apt-repo.yml`: bumped `actions/checkout` from `v4` to `v5` to clear a GitHub Actions deprecation warning ("Node.js 20 is deprecated... actions/checkout@v4 forced to run on Node.js 24") — cosmetic, did not affect the `2.6.1` build/publish, which succeeded

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
