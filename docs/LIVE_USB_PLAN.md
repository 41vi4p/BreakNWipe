# Bootable custom-branded live Linux USB for BreakNWipe

**Status: planning / research only — nothing described here is implemented yet.** This document
captures the implementation plan as designed on 2026-07-04; it realizes the "Bootable ISO/USB"
item already listed in `README.md`'s planned-features checklist and `docs/DESIGN.md`'s
"Portable Mode" section.

## Context

BreakNWipe normally requires installing onto a running OS and pointing it at *other* drives —
but you can never wipe the disk your own OS is booted from while it's running. A bootable live
USB (à la DBAN/ShredOS) solves exactly this: boot the target machine from the stick, and now its
internal disk is just an idle block device, safely wipeable start-to-finish. This is already
listed as a planned-but-unimplemented feature in the project's own docs (`README.md` "Bootable
ISO/USB — standalone offline wiping environment (custom OS)"; `docs/DESIGN.md` "USB bootable
image" / "Live CD/DVD creation scripts"), so this is realizing an existing vision, not scope
creep. For an IT-asset-recycling tool this is arguably the most operationally important delivery
format: a technician boots one USB on any machine, wipes it, done — no Linux knowledge required.

Two things surfaced during planning that must be treated as v1 requirements, not polish:
- **Certificate persistence.** `CertificateGenerator.__init__` (`breaknwipe/certificate/generator.py:44-45`) defaults the output directory to `os.path.expanduser("~/breaknwipe_reports")`. On a live boot running as root that's `/root/breaknwipe_reports`, which lives on the ephemeral live rootfs and is lost on reboot. The certificate is the entire deliverable of this tool — if it evaporates when the technician powers off, the live-boot exercise proves nothing. This must be solved in v1.
- **Secure Boot / disk visibility.** A self-built, unsigned image will not boot on Secure-Boot-enabled machines (a common default), and an over-trimmed kernel/firmware set can leave the very disk you want to wipe invisible. Both look like "the machine is broken" to a non-Linux technician, so the image needs a real `linux-generic` + curated firmware, hybrid BIOS+UEFI boot, and a documented "disable Secure Boot" instruction (signing is v2).

This plan is reviewable as code/config, but genuinely needs a QEMU smoke test (and ideally real
hardware) before anyone trusts it for a real wipe. That gate is called out explicitly in
Verification below.

## Approach

### 1. Tooling: `live-build`, Ubuntu base, with a documented Debian fallback
`live-build` (Debian's tool) is the right choice: it's driven entirely by a checked-in config
tree (no GUI, unlike Cubic — matching this repo's existing "every install path is a plain shell
script" style), and it automates the fragile parts (squashfs, live initramfs, hybrid BIOS+UEFI
bootloader) that a hand-rolled `debootstrap`+`mksquashfs`+`grub-mkrescue` build would leave for us
to get subtly wrong. Configure it against Ubuntu 24.04 LTS (`lb config --distribution noble
--mirror-bootstrap http://archive.ubuntu.com/ubuntu/ --archive-areas "main restricted universe
multiverse"` plus the Ubuntu archive keyring). **Caveat to document, not solve now:** Ubuntu
dropped official `live-build` support in favor of `livecd-rootfs` internally, so there's known
friction at the casper/keyring/systemd edges. Since the actual package needs (`hdparm`,
`nvme-cli`, `smartmontools`) are identical on Debian, document a same-day fallback: flip
`--distribution` to a Debian stable codename if Ubuntu-specific breakage blocks progress — the
resulting appliance is functionally identical either way.

### 2. Base image: minimal console-only, but don't starve the kernel/firmware
Bootstrap minbase-equivalent (`--variant=minbase`) against the Ubuntu noble suite. No X11/Wayland
desktop — `breaknwipe/cli/interactive.py`'s existing Rich-based wizard is the entire UI, keeping
the image small and boot fast. Do include a real `linux-generic` kernel and a curated
`linux-firmware` subset (starving this is how the target disk becomes invisible), plus `casper`
(or `live-boot`), `systemd-sysv`, `hdparm`, `nvme-cli`, `smartmontools`, `util-linux`, `parted`,
`rsync`, `ca-certificates`. The FastAPI web GUI stays available but **off by default**: it costs
zero extra system packages (already in `pyproject.toml`, lives in the uv venv), so ship it as a
second, explicit GRUB boot entry ("BreakNWipe — Network GUI mode" → `breaknwipe --gui --host
0.0.0.0`) rather than binding `0.0.0.0` unconditionally on an untrusted recycling-floor LAN.

### 3. Provisioning BreakNWipe inside the chroot — reuse `install.sh`'s pattern, with two required deviations
A live-build chroot hook (`config/hooks/live/9000-install-breaknwipe.hook.chroot`) replicates
`scripts/install.sh`'s approach: rsync the repo source to `/opt/breaknwipe/src` (same excludes as
`install.sh` — `.git .venv __pycache__ *.egg-info build dist node_modules`), run `uv sync
--no-dev` there, and generate the same wrapper script pattern (`/usr/local/bin/breaknwipe` execs
`.venv/bin/python -m breaknwipe.cli.main`). Two things must differ from the existing scripts,
because they assume an interactive `sudo` invocation that doesn't exist in a chroot build:
- **Install `uv` system-wide to `/usr/local/bin/uv` (pinned version)**, not per-`$SUDO_USER` the way `scripts/install_dependencies.sh` does — there is no `SUDO_USER` inside a chroot.
- **Let uv provision Python itself** (`uv python install`) rather than `apt install python3` — minbase has no Python, and this keeps "uv is the single source of truth" (per `CLAUDE.md`) true even at the OS-image level.

Package list lives in `config/package-lists/breaknwipe.list.chroot`. Keep `build-essential
libssl-dev libffi-dev` only for the `uv sync` step, then **purge them in a late cleanup hook**
(`config/hooks/live/9500-cleanup.hook.chroot`) before the squashfs is sealed — shrinks the image
and removes a compiler toolchain from what is otherwise a single-purpose security appliance.
`scripts/build_live_iso.sh` (not the hook) is what rsyncs the actual repo checkout into
`config/includes.chroot/opt/breaknwipe/src/` right before `lb build` — the source itself is never
committed into the live-build config tree.

### 4. Auto-launch on boot — agetty autologin + a wrapping launcher loop
- Autologin root on tty1 via `config/includes.chroot/etc/systemd/system/getty@tty1.service.d/override.conf` (standard `agetty --autologin root` override).
- `/root/.bash_profile` (shipped via `includes.chroot`), guarded to tty1 only (so other ttys still get a normal shell): if on tty1, `exec breaknwipe-live-launcher`.
- **New file `/usr/local/sbin/breaknwipe-live-launcher`** is required because `InteractiveMode.run()` (`breaknwipe/cli/interactive.py:31-42`) simply `return`s on completion/no-devices/cancel — it does not loop or offer a reboot/shutdown prompt. The launcher must own that loop: banner (ASCII logo/MOTD) → `breaknwipe --interactive` → on exit present `[w]` wipe another / `[g]` start network GUI / `[s]` root shell / `[r]` reboot / `[p]` poweroff. This is what actually delivers the "boot, wipe, done" experience for a non-Linux technician — without it they'd land on a bare shell after one wipe.
- **Certificate persistence (v1 requirement):** the launcher (or a wrapper around the `breaknwipe wipe`/`--interactive` invocation) must point the certificate output directory at somewhere that survives reboot — either a small FAT32/ext4 **persistence partition on the boot USB itself** (label `breaknwipe-certs`, auto-mounted by the launcher before invoking BreakNWipe, e.g. via `--output-dir` if the CLI supports it, or by symlinking `~/breaknwipe_reports` to the mounted partition), or a documented fallback of auto-detecting and copying to any *other* attached USB drive. Pick the boot-USB persistence-partition approach for v1 — it needs no second device and matches how DBAN-style tools handle logs.

### 5. Branding — concrete, deliberately lightweight for a console appliance
- **Bootloader menu:** live-build `config/bootloaders/grub-pc/grub.cfg` with custom entries ("BreakNWipe — Wipe this machine", "BreakNWipe — Network GUI mode", "Boot from first hard disk"), background image converted from the existing `breaknwipe/breaknwipe-gui/public/breaknwipe_logo1.png`.
- **Plymouth splash: skip for v1.** A console-only appliance doesn't need graphical boot theming; a quiet/verbose text boot is fine. This is v2 polish.
- **os-release / MOTD / issue:** ship `config/includes.chroot/etc/os-release` (`NAME="BreakNWipe Live"`, `PRETTY_NAME="BreakNWipe Live <version> (Ubuntu 24.04)"`), `/etc/motd`, `/etc/issue` with an ASCII banner. Cheap, high-signal branding.
- **Terminal colors:** nothing to do — the CLI already uses Rich, which auto-detects the Linux console's color support and degrades gracefully; just ensure `TERM` is set correctly by the getty override.

### 6. New files / repo layout
```
live-build/
  auto/config                                          # lb config: distribution noble, arch amd64, archive-areas, bootloaders
  config/package-lists/breaknwipe.list.chroot           # hdparm nvme-cli smartmontools util-linux parted rsync ca-certificates linux-generic ...
  config/hooks/live/9000-install-breaknwipe.hook.chroot # pinned system-wide uv + uv sync --no-dev + wrapper (install.sh pattern, chroot-adapted)
  config/hooks/live/9500-cleanup.hook.chroot            # apt purge build-essential/*-dev, strip apt caches
  config/includes.chroot/etc/systemd/system/getty@tty1.service.d/override.conf
  config/includes.chroot/usr/local/sbin/breaknwipe-live-launcher
  config/includes.chroot/root/.bash_profile
  config/includes.chroot/etc/{os-release,motd,issue}
  config/bootloaders/grub-pc/                           # grub.cfg + splash.png (derived from breaknwipe/breaknwipe-gui/public/breaknwipe_logo1.png)
scripts/build_live_iso.sh                                # driver script, matching existing scripts/ bash style (set -e, print_status/etc, main() with phase functions)
```

`scripts/build_live_iso.sh` phases: `check_build_host` (must run on a Debian/Ubuntu host with
`live-build` installed, as root) → `stage_source` (rsync the repo checkout into
`config/includes.chroot/opt/breaknwipe/src`) → `lb clean` → `lb config` → `lb build` →
`report_artifact`. Add `Makefile` targets: `iso` (`sudo ./scripts/build_live_iso.sh`) and an
explicit-confirmation `live-usb` target requiring `DEVICE=/dev/sdX` before `dd`-ing (this
destroys the target USB — require a typed confirmation, same caution as any other destructive
Makefile target in this repo). Document loudly in `make help` that this build is heavyweight,
needs several GB and root, uses loop devices, only runs on a Debian/Ubuntu host, and should never
be auto-invoked.

### 7. Output artifact + docs
Resulting file: `live-build/live-image-amd64.hybrid.iso` (isohybrid, `dd`-able), renamed to
`breaknwipe-live-amd64.iso`. New README section "Bootable ISO/USB" (flips the `[ ]` checkbox in
the planned-features list to `[x]`): how to flash (`dd`, Rufus in DD mode, Ventoy, balenaEtcher —
all destroy the USB, say so), the Secure-Boot-must-be-disabled caveat, and how certificate
persistence works. `docs/CHANGELOG.md` entry + version bump per the project's own versioning
policy, once this is actually implemented.

### Explicitly out of scope for v1 (future polish)
Plymouth graphical boot splash; making the network GUI boot entry default-on; auto-detecting and
saving certificates to a second external USB as an alternative to the persistence partition;
aggressive image size trimming / fully pinned reproducible builds; Secure Boot image signing.

## Verification

Nothing here is trustworthy from code review alone — this is a physically destructive tool, and a
silent boot failure or a wizard that reaches a half-broken install is exactly the failure mode to
avoid, same as with any other change to the wiping path.

1. **Provisioning dry-run without building a full ISO:** bootstrap a throwaway Ubuntu/Debian minbase container, run the `9000-install-breaknwipe` hook logic directly inside it, confirm `uv sync --no-dev` succeeds and `breaknwipe --interactive` starts.
2. **`breaknwipe-live-launcher` loop:** exercise it standalone in an ordinary shell (not yet booted from the ISO) to confirm the menu logic (wipe again / GUI / shell / reboot / poweroff) behaves.
3. **QEMU boot smoke test (mandatory before trusting this on real hardware):**
   - BIOS: `qemu-system-x86_64 -m 2G -cdrom breaknwipe-live-amd64.iso -drive file=scratch.img,format=raw -boot d`
   - UEFI: same, plus `-bios /usr/share/OVMF/OVMF_CODE.fd` (or equivalent OVMF firmware)
   - Confirm: the ISO boots on both, casper mounts the squashfs, autologin fires, the wizard appears within seconds with no manual login step, device detection sees the scratch virtual disk, a full wipe runs to completion, and — critically — **the certificate is produced and still present after a reboot** (persistence partition round-trip).
4. Only after the QEMU pass succeeds, test on real (ideally disposable) hardware: confirm Secure Boot must be disabled as documented, and that the real disk (not just a QEMU scratch image) is visible and wipeable.
