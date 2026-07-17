# Changelog

All notable changes to BreakNWipe are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/). Every change to the codebase increments the version in `breaknwipe/__init__.py` and `pyproject.toml`.

## [3.11.2] - 2026-07-17

### Fixed
- **Docker publish workflow failing on manual `workflow_dispatch` runs** — `docker/build-push-action`
  errored with "tag is needed when pushing to registry" because every rule in
  `docker/metadata-action`'s `tags:` config in `.github/workflows/docker-image.yml` was gated on
  being on a `v*` tag ref (two `type=semver` rules plus `latest` behind
  `startsWith(github.ref, 'refs/tags/v')`). The workflow's own trigger list includes
  `workflow_dispatch`, but a manual run off a branch produces none of those, so
  `steps.meta.outputs.tags` came back empty and `buildx` got no `--tag` at all. Added a
  `type=sha,format=short` rule enabled only for `workflow_dispatch`, so manual runs (e.g. to
  smoke-test a Dockerfile change) get a real, non-`latest` tag instead of failing or silently
  overwriting the release tag.

## [3.11.1] - 2026-07-17

### Fixed
- **Docker image vulnerability hygiene** — the container build (`Dockerfile`) now runs
  `apt-get upgrade -y -qq` right after `apt-get update` in both the `python-builder` and runtime
  stages, before installing packages. The `ubuntu:24.04` base tag is only rebuilt periodically, so
  packages already baked into its layers can trail behind Ubuntu's published security patches at
  build time even though `apt-get install` pulls current versions of the packages we explicitly
  list. Confirmed against Ubuntu noble's archive that this resolves `CVE-2026-41992`/`-41991`
  (gzip, fixed in `1.12-1ubuntu3.2`), `CVE-2026-5704` (tar, fixed in `1.35+dfsg-3ubuntu0.3`), and
  `CVE-2026-56136`/`-46571` (ntfs-3g, fixed in `1:2022.10.3-1.2ubuntu3.2`) — all were sitting on
  stale pre-security-update versions baked into the base image tag, not versions we pin ourselves.
  - `CVE-2018-11739`/`CVE-2018-11740` (sleuthkit, OOB reads in `raw.c`, CVSS 8.1 per NVD) and
    `CVE-2025-66382` (expat, quadratic-time DoS parsing a ~2 MiB crafted XML file) remain flagged
    with no fix version available in Debian/Ubuntu — Debian's tracker rates the TSK pair
    "Negligible" impact (requires processing a maliciously crafted raw disk image, which isn't how
    `device/recovery.py` invokes `fls`/`icat` — against the operator's own attached hardware, not
    untrusted image files) and lists the expat one as "postponed" pending an upstream fix.
    Documented here as accepted/won't-fix risk rather than something to chase — no patched package
    exists to move to for any of the three.

## [3.11.0] - 2026-07-08

### Added
- **File Shredder** — a new pillar (`/shred` in the GUI, `breaknwipe shred` on the CLI) that
  securely overwrites and deletes specific files on a mounted drive, leaving the rest of it
  untouched. Reuses the existing pass/pattern machinery (`wipe_engine.algorithms.create_algorithm`
  — including the REA crypto-erase family, which is pure byte generation with no device
  dependency) and the same seek/write/flush/fsync durability idiom as
  `wipe_engine.engine.WipeEngine._execute_pass`, applied to a file's own byte range instead of a
  device's.
  - New `breaknwipe/device/shredder.py`: `list_directory()` (read-only browsing, mount-anchored),
    `assess_reliability()` (SSD/NVMe wear-leveling and copy-on-write filesystem detection — see
    below), and `shred_files()` (per-file overwrite + truncate + rename + unlink, mirroring GNU
    `shred -u`'s hardening). Every file path is independently re-validated to resolve inside the
    partition's own mount point on every call — defense in depth, never trusting that a path only
    came from a prior directory listing (the same posture as the existing `/api/download`
    allowlist and `recovered_roots` check). Symlinks are refused outright, checked on the raw,
    unresolved path *before* any realpath resolution — an initial implementation checked the
    already-resolved path instead, which silently followed the symlink and shredded its target
    (inside or outside the mount) rather than refusing; caught and fixed via
    `tests/test_shredder.py` before release. Hard-linked files are shredded but surface a warning
    (other names pointing to the same data are also affected).
  - **Honest reliability caveat, not a hard gate**: in-place overwrite can't be guaranteed to
    destroy data on SSD/NVMe drives (wear-leveling may write to different physical cells) or on
    copy-on-write filesystems (btrfs, zfs — a write never touches the original blocks). Both are
    detected and surfaced as a specific warning in the GUI and CLI; the shred still proceeds,
    matching the honest-limits stance the Recovery/Verify pillars already take about their own
    boundaries.
  - Web: `GET /api/shred/reliability`, `GET /api/shred/browse`, `POST /api/shred/start`,
    `GET /api/shred/{job_id}`, `POST /api/shred/{job_id}/cancel`, `WS /ws/shred/{job_id}` — the
    fourth near-identical background-job manager (`shred_manager.py`, copied from
    `verify_manager.py`'s pattern) after wipe/recovery/verify. Deliberately not refactored into a
    shared base class in this change — that's flagged as a separate, focused follow-up rather than
    bundled with a feature addition.
  - GUI: file browser with breadcrumb navigation, client-side search, `Set`-based multi-select
    with select-all (persists across folder navigation), the same category→algorithm picker as
    Wipe (extracted into a new shared `components/algorithm-picker.tsx`), a typed
    (`"shred"`) confirmation dialog, live WebSocket progress, and a per-file results list.
  - CLI: `breaknwipe shred PARTITION FILES... [--algorithm NAME] [--force]`.
  - Scope: files only in this release — folders are browsable but not recursively shreddable
    (a natural follow-up once the file-level path is proven).

## [3.10.0] - 2026-07-08

### Added
- **Rich wipe-completion results panel in the GUI.** The wipe page previously showed one "Wipe
  completed." line + a PDF button; it now fetches the (previously unused) rich
  `GET /api/wipe/report/{session_id}` endpoint on completion and renders: stat tiles (algorithm +
  passes, duration + finish time, data wiped + average speed, verification pass/fail), a drive
  detail table (path, model, serial, capacity, interface/type, report ID), and — when a certificate
  was generated — a "Certificate of destruction" card with the verification **QR code image**
  (served via `/api/download` from the PNG the PDF build already wrote), a blockchain-anchor row
  (tx hash + Sepolia Etherscan link) when anchored, and PDF/JSON download buttons. The old minimal
  block remains as the fallback for failed/cancelled wipes or if the report fetch fails.
- **Reports page now actually shows past wipes, with downloads.** Two fixes: (1) the DB insert
  (`store_wipe_report`) only ran inside the certificate-generation success path, so
  certificate-less or cert-failed wipes were never recorded — it now runs for **every finished
  wipe**; (2) the page only rendered device path/algorithm/date — cards now show model, serial,
  success/failed badge, bytes written, speed, report ID, a QR thumbnail, and working PDF/JSON
  download buttons (records without a certificate say so instead). `qr_code_image_path` is now
  actually populated in the DB (the `qr_data` argument was never passed before).
- `GET /api/wipe/report/{session_id}` response extended with `verification` (`enabled`/`passed`,
  from the engine's `result.verification_passed`, newly stashed on the session), `certificate`
  (`pdf_path`/`json_path`/`qr_png_path`), and `blockchain` (`tx_hash`/`report_hash`/`explorer_url`)
  sub-objects. `CertificateGenerator.generate_certificate()` now returns the standalone QR PNG path
  as `qr_png` (it was always written next to the PDF but never surfaced).
- `docker-compose.yml`: new `breaknwipe-history` volume for `/root/.breaknwipe` so the wipe-history
  DB (Reports/Logs pages) survives container restarts; documented in `docs/DOCKER.md`.

### Fixed
- **Post-wipe verification no longer fails on correctly wiped devices.** Two heuristic bugs in
  `WipeVerifier._contains_recoverable_data()`: (1) an all-zeros sample made every byte a "null
  position" with perfectly regular gaps, so `_contains_structured_patterns()` flagged 100% of
  samples on a zero-filled device — the canonical successful wipe always failed verification (and
  `breaknwipe verify` reported "NOT fully erased" on it); (2) the text-pattern check flagged any
  sample containing `'@'`+`'.'` or >3 `'/'` characters, which ~every 4 KiB of random bytes contains
  by chance, so random-fill/REA wipes always failed too. Fixed with two short-circuits before the
  pattern checks: ≥90% uniform fill (0x00/0xFF) and entropy ≥7.5/8 are wipe residue, not
  recoverable data. Real data is still detected (text, structured low-entropy patterns, and known
  file signatures in high-entropy data via the separate `_check_file_signatures()` pass).
  Discovered because the new results panel surfaces the verdict prominently; also fixes the same
  false negatives in the GUI's Verify pillar (`erasure_check.py` shares this sampling code).
- **`WipeSession` silently rejected the dynamic `qr_data` attribute** (pydantic models raise on
  undeclared attributes), which aborted the certificate post-processing mid-way inside its
  try/except every time — the true root cause of the always-empty Reports page even for certified
  wipes. `qr_data`, `verification_passed`, and `certificate_files` are now declared model fields.
- **Certificates no longer claim "BreakNWipe 1.0".** `WipeReport.software_version` had a hardcoded
  `"BreakNWipe 1.0"` dataclass default that nothing ever overrode, so every PDF/JSON/HTML
  certificate and blockchain payload carried it (the PDF footer even rendered
  "BreakNWipe vBreakNWipe 1.0"). It now defaults to `breaknwipe.__version__`; the `from_dict`
  fallback for reports missing the field is `'unknown'` (deliberately not the current version —
  a re-loaded old report shouldn't claim it was generated by today's build). QR payload *schema*
  version tags (`1.0`/`2.0`) are format versions and are intentionally unchanged.
- FastAPI app `version` (OpenAPI docs) was hardcoded `1.0.0` → now `__version__`; `/api/system-info`
  now includes a "BreakNWipe Version" entry, which the About page's System card renders.
- **The GUI's Reports page source was never in git.** `.gitignore`'s unanchored `reports/` (and
  `recover/`) patterns matched *any* directory of that name at any depth — including
  `breaknwipe-gui/app/reports/` — so `app/reports/page.tsx` existed only on disk. Patterns are now
  anchored to the repo root (`/reports/`, `/recover/`) and the page is tracked.

## [3.9.0] - 2026-07-08

### Added
- **Docker image** — pull, attach a drive, use the web GUI from the host browser; nothing
  installed on the host. New root-level `Dockerfile` (multi-stage: Node 20 builds the Next.js
  static bundle; `uv sync --no-dev --managed-python` vendors Python + deps at `/opt/breaknwipe`,
  the exact layout/paths of `scripts/build_packages.sh` since uv bakes absolute paths; runtime is
  Ubuntu 24.04 + only the system tools the engine shells out to — including `e2fsprogs`,
  `dosfstools`, `exfatprogs`, which `device/fsck.py` needs but the `.deb` dependency list never
  declared). ENTRYPOINT is the CLI with the GUI (`--gui --host 0.0.0.0 --port 8000`) as the
  default CMD, so `docker run ... breaknwipe --list-devices` and friends also work. gparted and
  adb/fastboot deliberately not installed (headless container; both features self-disable via
  their `shutil.which` guards).
- **`docker-compose.yml`** — one-command GUI run (privileged, `/dev` + `/run/udev` binds, named
  volume persisting `/root/breaknwipe_reports`).
- **`.github/workflows/docker-image.yml`** — builds linux/amd64 + linux/arm64 via buildx/QEMU and
  pushes `:X.Y.Z`, `:X.Y`, `:latest` to Docker Hub on every `v*` tag push. Requires
  `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` repo secrets, set up manually per `docs/DOCKER.md`
  (same stance as the APT repo's GPG key: credentials are never handled by scripts).
- **`docs/DOCKER.md`** — usage + an honest per-platform support matrix: **Linux** full device
  access (`--privileged -v /dev:/dev`, or scoped `--device /dev/sdX` for overwrite-only wiping);
  **Windows** USB drives only, forwarded into the WSL2 VM with `usbipd-win` (internal SATA/NVMe
  never visible; attach doesn't survive replug); **macOS** no device access at all (Docker
  Desktop's VM has no block/USB passthrough) — container runs as a UI/API demo only. Also covers
  report persistence, blockchain `.env` mounting, the no-auth-on-port-8000 warning, and the
  one-time Docker Hub maintainer setup.
- `make docker-build` / `make docker-run` targets; `.dockerignore`; README Docker install
  section + badge.

## [3.8.0] - 2026-07-07

### Added
- **In-GUI Help & documentation page** (`/help`, reachable from a new Help icon in the top bar's
  secondary group). One page, with a sticky section nav, covering: getting started (install
  commands, launch modes, the root requirement); step-by-step usage guides for all four pillars
  (Wipe's category→algorithm→confirm flow, Recover's quick-vs-deep scan and same-device refusal,
  Verify's depths and read-only sampling, Disk Utility's health/partition-map/fsck/hex-viewer
  panels); certificates/blockchain-anchoring/QR-verification and the audit log; a full algorithm
  reference **rendered from `lib/algorithms.ts`** (the same data the Wipe picker uses, so the help
  page can't drift from what the GUI actually offers); a complete CLI reference documenting every
  command (`wipe`, `info`, `fsck`, `resize`, `recover`, `verify`, `list-algorithms`,
  `verify-certificate`, `batch`) with option tables and copyable examples — `batch` and
  `verify-certificate` honestly badged "in progress" since their implementations are stubs, and the
  REA family noted as GUI-only since the CLI `wipe --algorithm` choice list doesn't include it; and
  a 15-question FAQ (why root, algorithm choice, SSD multi-pass myths, recovery-after-wipe honesty,
  same-device output refusal, certificate verification flow, safety gates, REA, remote GUI access
  caveat, HPA/DCO, update/uninstall).

## [3.7.3] - 2026-07-07

### Fixed
- **`.deb` postinst no longer tries to enable a systemd service that was never packaged.**
  `scripts/build_packages.sh`'s generated `postinst`/`prerm` unconditionally ran
  `systemctl enable/disable/stop breaknwipe-daemon`, but the `.deb` package's file list only ever
  ships `opt/breaknwipe` and the `usr/bin` entry points — no `breaknwipe-daemon.service` unit is
  packaged (unlike `scripts/install.sh`'s manual `make install-system` path, which actually
  generates that file). The stray `|| true` kept installs from failing, but every `apt install
  breaknwipe` printed a confusing `Failed to enable unit: Unit file breaknwipe-daemon.service does
  not exist.` warning. Removed the dead systemd enable/disable/stop/reload calls from the
  `.deb`-only postinst/prerm/postrm scripts; BreakNWipe runs on demand
  (`breaknwipe --interactive`/`--gui`), not as a background daemon, via the apt install path.

## [3.7.2] - 2026-07-07

### Changed
- **Logo shown large where it needs detail to read.** The landing-page hero now has a two-column
  layout — headline/copy/pillars on the left, the logo large (up to 256px) on the right with a
  gentle continuous float and a soft brand-tinted drop shadow — and the About page's project badge
  grew from a 44px icon-sized crop to a 144px image alongside the title/description. At the small
  sizes used before, the logo's badge details (shield, disk, lightning bolt, wraparound text)
  weren't legible; the top-bar/favicon uses stay small since those are just recognition marks, not
  meant to be read in detail.

## [3.7.1] - 2026-07-07

### Changed
- **New logo** (`breaknwipe/breaknwipe-gui/public/breaknwipe_logo1.png`) — replaces the placeholder
  shield icon in the GUI's top-bar brand mark and the About page's project badge, generated into a
  proper multi-resolution (16/32/48/64px) `favicon.ico`, and now the image the README displays.
  Retired the old `frontend_ui/images/logo.png` reference.

## [3.7.0] - 2026-07-07

### Changed
- **Algorithm picker in the Wipe flow is now a two-step card flow, not a dropdown.** First pick a
  category — Standard, REA (crypto-erase), or Custom — each with its own description of what that
  family of algorithms actually does; picking one reveals only that category's algorithms as cards
  (name, pass count, a real description grounded in `wipe_engine/algorithms.py`'s actual pass
  sequences, and an "avoid on SSD/NVMe" note for the HDD-oriented ones: DoD 7-pass, Gutmann, REA
  Extreme), instead of one long flat list mixing all 13 together. The three configurable algorithms
  (Random, Custom pattern, REA Custom) moved into their own "Custom" category rather than being
  buried inside Standard/REA. Switching category auto-selects that category's first algorithm, so
  the wipe button never silently carries over a stale pick from a different category. Selection uses
  the same bordered-card + ring-glow highlight already used for the Recover/Verify mode toggles.

## [3.6.1] - 2026-07-07

### Fixed
- **Critical: fixed-pattern wipe passes were not writing their claimed byte values.**
  `wipe_engine/algorithms.py` used doubled-backslash byte literals (`b'\\x00'` — four literal ASCII
  characters, backslash/x/0/0) instead of real byte literals (`b'\x00'`, the actual null byte) for
  every zeros/ones pass and every Gutmann fixed pattern, across NIST Clear/Purge, DoD 3-pass/7-pass,
  Gutmann, and the REA family's overwrite phases. Since `engine.py` writes `WipePass.pattern` to the
  device byte-for-byte, this meant e.g. "Zero Fill" was writing the literal text `\x00\x00\x00...`
  repeating, not actual zero bytes — the same escaping bug found and fixed earlier in
  `verification.py`'s file-signature list, but here affecting the wipe engine itself, not just an
  ancillary check.
  **Impact:** every affected pass still overwrote the original data with *some* deterministic byte
  value, so recoverability of prior data was very likely unaffected — but the tool was not actually
  writing the NIST SP 800-88 / DoD 5220.22-M / Gutmann patterns its algorithm names and certificates
  claimed. Any certificate generated for a fixed-pattern algorithm before this fix does not accurately
  describe the bytes that were written. Only the fully-random passes (`_generate_random_block()`,
  `_generate_rea_pattern()`, both backed by `os.urandom()`) were unaffected. Found while investigating
  an unrelated GUI change; verified the fix end-to-end by writing each pass to a loopback file and
  confirming the on-disk bytes now exactly match the claimed pattern (all-`0x00`, all-`0xFF`, Gutmann's
  specific bit sequences).

## [3.6.0] - 2026-07-06

### Added
- **"Open GParted" escape hatch in Disk Utility.** BreakNWipe's own partition tools (grow/shrink/move)
  deliberately don't try to cover everything a partition editor can do (changing partition types,
  complex multi-partition layouts, etc.) — a callout on the partition map now offers to launch GParted
  directly for those cases, via `GET /api/utility/gparted` (availability check) and
  `POST /api/utility/gparted/launch` (fire-and-forget `subprocess.Popen`, since GParted is a separate
  desktop process BreakNWipe doesn't need to track). Shows an install hint (`sudo apt install gparted`)
  when it isn't present instead of hiding the option outright. Only works when the server has a
  graphical session to launch into (the normal case: `sudo breaknwipe --gui` started from the user's
  own desktop terminal, which is how this app is meant to run).
- Landing-page hero polish: removed a confusing Easter egg (the literal bytes `0f 9d 63` — the hex
  code of the brand's primary color — were hardcoded and highlighted in the decorative background
  texture *and* repeated in a foreground badge with unclear copy, visually colliding). Replaced with
  a slow-drifting ambient glow, dual scan lines sweeping the hex-dump texture on staggered loops, a
  periodic byte-flicker effect (simulating live reads, client-side only so there's no hydration
  mismatch), and a staggered fade-in for the hero copy and pillar tiles on load.

## [3.5.0] - 2026-07-06

### Added
- **Progress bar, ETA, and cancel for erasure verification.** Unlike deep-scan recovery (an external
  PhotoRec process with no scripted progress API), `WipeVerifier`'s sampling loop is our own Python
  code, so progress tracking needed no polling hacks: `verify_wipe_detailed()` now accepts a
  `progress_callback` (invoked after every sample with exact `samples_done`/`total_samples`/`percent`/
  `eta_seconds`) and a `cancel_event`, checked before each sample so a long paranoid-depth check can be
  stopped early. Refactored the three verification depths (quick/comprehensive/paranoid) onto a shared
  `_run_samples()` loop to avoid tripling this logic.
- `device/erasure_check.py`'s `check_erasure()` forwards both through to `WipeVerifier`, emitting its
  own `sampling` → `cross_checking` → `completed`/`cancelled` status transitions (cancellation is also
  honored between partitions during the recovery cross-check phase, not just during sampling).
- New `web/verify_manager.py` (`VerifySessionManager`), mirroring `RecoverySessionManager`: erasure
  checks run as background jobs. `POST /api/verify/erasure/start` returns a `job_id` immediately,
  progress streams over `WS /ws/verify/{job_id}`, `GET /api/verify/erasure/{job_id}` polls the same
  state for reconnects, and `POST .../cancel` stops one early. The GUI's `/verify` page now shows a
  progress bar, samples-done counter, ETA, and a Cancel button while checking, matching the wipe and
  deep-scan-recovery progress UIs. The CLI's `breaknwipe verify` gained a matching Rich progress bar.

## [3.4.0] - 2026-07-06

### Added
- **Deep-scan recovery progress + ETA** — `deep_scan_recover()` now runs PhotoRec via `Popen` and polls
  `/proc/<pid>/io`'s `read_bytes` once a second (the only externally observable progress signal in
  PhotoRec's unattended `/cmd` mode — it doesn't move its file descriptor's offset, so
  `/proc/<pid>/fdinfo/pos` is useless). Reports percent (clamped below 100 until the process actually
  exits, since PhotoRec fast-skips empty/duplicate regions), rate, and ETA. A new
  `RecoverySessionManager` (mirroring `WipeSessionManager`) runs deep scans as background jobs —
  `POST /api/recovery/deep-scan/start` returns a `job_id` immediately, progress streams over
  `WS /ws/recovery/{job_id}`, and the GUI's "Start deep scan & recover" now shows a live progress bar,
  scanned-bytes counter, rate, running "found so far" count, ETA, and a Cancel button.
- **Browse and preview recovered files from the GUI** — recovered-file lists (both quick-scan/icat and
  deep-scan results) are now clickable; a new `GET /api/recovery/view` endpoint streams a recovered
  file's bytes for inline preview (images, PDFs via `<iframe>`, text files) or download/"open in new
  tab" for everything else. Only readable from folders a recovery operation actually wrote to during
  the server's lifetime (`self.recovered_roots`) — the client supplies a file path but never a root,
  so this can't become an arbitrary local file read.
- **Verify pillar — confirms a device was actually wiped clean** (not certificate authenticity). Pick a
  device and run a read-only check: statistical sampling of the raw drive (Shannon entropy, repeated-
  pattern, and known file-signature detection, at quick/comprehensive/paranoid depth) plus a best-effort
  recovery cross-check on any still-recognizable filesystem — no recognizable filesystem at all is
  itself treated as a good sign, not a failure. New `breaknwipe/device/erasure_check.py`
  (`check_erasure()`), `POST /api/verify/erasure`, and `breaknwipe verify <device>` CLI command.
  Along the way, fixed a real bug in `wipe_engine/verification.py`'s file-signature list: the byte
  literals were double-escaped (`b'\\x89PNG'`, seven literal ASCII characters) instead of real bytes
  (`b'\x89PNG'`), so binary file-signature detection had never actually matched anything. Also
  refactored `WipeVerifier` to expose a `verify_wipe_detailed()` method returning full stats (entropy,
  pattern %, signature hits with offsets) alongside the existing bool-returning `verify_wipe()` that
  the wipe engine's own post-wipe check already relied on.
- A separate `POST /api/verify/certificate` endpoint (digital-signature + blockchain-anchor check via
  `CertificateGenerator`) was built during this work but isn't linked from the GUI nav — the "Verify"
  pillar is about erasure, not certificate authenticity. Left in place as a working API for a possible
  future certificate-verification surface.
- **Full GUI redesign** — replaced the generic sidebar-dashboard layout with a proper information
  architecture: a clean landing page (`/`) with a hero and four clearly-styled pillar actions — Wipe,
  Recover, Verify, Disk Utility (each color-coded by nature: danger/info/success/primary) — instead of
  opening straight into a device list. Navigation is now a horizontal top bar with the four pillars as
  primary tabs (suppressed on the landing page itself) and Logs/Reports/About tucked into compact
  tooltip icon buttons. The old device-list landing page moved to `/utility` (the Disk Utility pillar's
  entry point); `/wipe` and `/recover` each gained their own in-flow device picker (a new shared
  `<DevicePicker>`/`<DeviceCard>` pairing) so every pillar is a self-contained starting point rather
  than assuming a device was already chosen elsewhere.
- **Fixed a latent bug**: PhotoRec writes its `photorec.log` into the *current working directory* of
  the process (undocumented behavior, found by testing directly), not the output folder — previously
  this could leak stray `photorec.log` files into wherever the FastAPI/CLI process's cwd happened to
  be. `deep_scan_recover()` now runs PhotoRec with `cwd=output_dir` and excludes `photorec.log` from
  the recovered-files count.

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
