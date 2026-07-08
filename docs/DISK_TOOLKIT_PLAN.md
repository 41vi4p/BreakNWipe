# BreakNWipe → complete disk toolkit — roadmap

**Status: Phases 1–6 all shipped** (the header previously said 1–4, stale since Phase 5 landed;
corrected here alongside adding Phase 6). This document is the roadmap for growing
BreakNWipe from a secure-wipe utility into a general-purpose, genuinely usable disk toolkit — one
that beats GParted / testdisk / GNOME-Disks on *approachability* while keeping the wipe + tamper-
proof certificate as a flagship feature. The name stays **BreakNWipe**; positioning broadens.

## Why

Limiting the tool to "IT-asset-recycling secure wipe" leaves out the everyday developer/user who
just wants to do disk things without a confusing tool. Four concrete gaps to close:
1. A professional GUI with **light + dark themes** (the old GUI was dark-only static HTML).
2. **Easy partition resize/extend** — the classic "my VM/root was 20 GB, I grew the disk but root
   didn't expand" problem, which existing tools make needlessly confusing.
3. **Post-wipe sector/hex viewing** — actually *see* that a wipe worked.
4. **Deleted-file recovery** for drives that were deleted/quick-formatted but **not** wiped. (After
   a real BreakNWipe algorithm wipe, nothing is recoverable — the tool says so honestly.)

## Architecture: static-export Next.js SPA served by the existing FastAPI backend

The GUI is **Next.js 16 / React 19 / Tailwind v4 / TypeScript** (App Router), living at
`breaknwipe/breaknwipe-gui/` (a Node subproject *inside* the Python package, sibling of `web/` and
`device/` — analogous to how `blockchain/` is a subproject in the repo).

It is built as a **static-export SPA** (`output: 'export'` → an `out/` folder of HTML/CSS/JS;
client components fetch the REST/WebSocket API). The privileged device work stays in the Python
backend (it needs root; a Node server running as root would be worse). So the deployment model is
unchanged: **one `sudo breaknwipe --gui` launches one FastAPI server on one port**, now serving the
built Next bundle instead of `frontend_ui/`. Node is a **build-time-only** dependency; runtime is
still just the Python venv.

- **Dev:** `npm run dev` (Next :3000) + `sudo uv run python -m breaknwipe.cli.main --gui` (FastAPI
  :8000). The client reads an API base from `NEXT_PUBLIC_API_BASE` (`http://localhost:8000` in dev,
  empty in production → same-origin relative `/api` + `/ws`).
- **Prod:** `web/server.py` mounts `breaknwipe/breaknwipe-gui/out/` (located relative to itself) as
  the static root; `/api/*` and `/ws/*` stay as they are.
- `out/`, `.next/`, `node_modules/` are gitignored; the `.deb` bakes in `out/` because the Node
  build runs before the source is vendored.

## Phases

### Phase 1 — GUI foundation: redesign + theming + repositioning ✅ shipped (v3.0.0)
Stand up the Next app, a real light/dark design system, and re-implement **all existing features**
(device list, health, partitions, fsck, wipe + progress + certificate, logs, reports, about)
against the **unchanged** backend API. Retire the old `frontend_ui/` once at parity. Add a Node
build stage to `scripts/build_packages.sh` / `scripts/install.sh`. Broaden README/CLAUDE.md
positioning. Low risk — no backend logic changes except how static files are served.

### Phase 2 — Partition management: full resize (grow / shrink / move) + extend-root/VM flow ✅ *shipped (v3.1.0)*
New isolated `breaknwipe/device/partition.py` (same safety discipline as `fsck.py`), shelling out
to `growpart`, `parted`/`sfdisk`, `resize2fs`/`ntfsresize`/`xfs_growfs`/`btrfs`, and
`pvresize`/`lvextend` (LVM). Headline UX: **detect the situation and offer the one right action** —
grown disk → `growpart` + online fs-grow (ext4/xfs/btrfs grow while mounted, so root extends live,
no live USB); LVM + new disk → add PV → `lvextend -r`. Full grow/shrink/move with escalating gates:
grow is safe; shrink is fs-first-then-partition and refuses when mounted; move (block-copy + table
rewrite; `parted` removed `move`) is gated hardest and labelled experimental. Always preview the
exact commands; never auto-unmount; system-disk + typed-confirmation gates. Interactive partition-
map GUI. Adds `cloud-guest-utils`/`lvm2`/`xfsprogs`/`btrfs-progs`/`ntfs-3g` deps.

### Phase 3 — Hex / sector viewer (read-only) ✅ shipped (v3.2.0)
`read_sectors(path, offset, length)` (read-only, bounded chunk) + `GET
/api/devices/{path}/sectors`. Virtualized hex+ASCII GUI (windowed rendering for multi-TB devices),
"jump to offset", sector boundaries. Wired into the post-wipe flow to visually confirm zeros/pattern.

### Phase 4 — File recovery (heaviest) ✅ shipped (v3.3.0)
`breaknwipe/device/recovery.py`, two complementary modes (both shelling out to established forensic
tools, matching the project's subprocess pattern — chosen over the `pytsk3` C-binding for clean
packaging): *Quick scan* via **The Sleuth Kit** CLI (`fls` to enumerate deleted entries, `icat` to
extract by metadata address) recovers files **with original names** on NTFS/FAT/exFAT; *Deep scan*
via **PhotoRec** (`photorec`) signature-carves file bodies even when metadata is gone (ext4,
quick-format, damaged), without names. Scan (read-only) → browse (name/size/path, multi-select) →
restore to a **different** device (enforced in the module, not just the UI — refuses if the output
folder is on the source device). Honest framing: a fully-wiped drive is unrecoverable, stated in the
UI. `GET /api/recovery/available`, `POST /api/recovery/scan`, `POST /api/recovery/restore`; `/recover`
GUI page; `breaknwipe recover` CLI command. Adds `sleuthkit` + `testdisk` deps.

### Phase 5 — Progress/ETA, file browsing, real Verify, and a GUI redesign ✅ shipped (v3.4.0)
Follow-on polish after the four phases above landed: deep-scan recovery gained live progress + ETA
(`/proc/<pid>/io` polling — PhotoRec has no scripted progress API and doesn't move its fd offset, so
`fdinfo/pos` is useless) via a new `RecoverySessionManager` background-job pattern (mirrors
`WipeSessionManager`) streamed over `WS /ws/recovery/{job_id}`; recovered files became browsable and
previewable in-GUI (`GET /api/recovery/view`, restricted to folders a recovery operation actually
wrote to — the client never supplies a root); and a real **Verify** feature was built — confirms a
*device* has actually been wiped clean (not certificate authenticity): `device/erasure_check.py`
combines `WipeVerifier.verify_wipe_detailed()` (entropy/pattern/file-signature sampling of the raw
device) with a best-effort recovery cross-check on any still-recognizable filesystem. Fixed a real
bug found along the way: `verification.py`'s file-signature byte literals were double-escaped and had
never actually matched real binary data. Alongside this, the GUI's IA was redone: a proper landing
page (hero + four color-coded pillar actions) replaced the old device-list-as-homepage, navigation
became a horizontal top bar with those same four pillars as tabs, and `/wipe`/`/recover`/`/verify`/
`/utility` each gained their own in-flow device picker so no pillar assumes a device was already
chosen elsewhere. (A separate `POST /api/verify/certificate` signature/blockchain-check endpoint was
also built but is intentionally not linked from the GUI nav — it verifies certificate authenticity,
a different concern from the Verify pillar's device-erasure check.)

### Phase 6 — File Shredder ✅ shipped (v3.11.0)
A new pillar that destroys individual files rather than a whole device: pick a mounted partition,
browse/search its files in the GUI, multi-select, choose an overwrite algorithm, and only those
files' bytes are overwritten (then truncated/renamed/unlinked). Reuses `wipe_engine.algorithms`'
pass/pattern generation and `WipeEngine._execute_pass`'s seek/write/flush/fsync idiom, applied to a
file's own length instead of a device's — the REA crypto-erase family works here too, since it's
pure byte generation with no device dependency. New `device/shredder.py`, the fourth
background-job manager (`web/shred_manager.py`, following `verify_manager.py`'s pattern — a shared
base class was considered but deliberately deferred to its own follow-up rather than bundled with
this feature), and a `breaknwipe shred` CLI command. Detects (and warns about, without blocking)
the two cases where in-place overwrite can't guarantee destruction: SSD/NVMe wear-leveling and
copy-on-write filesystems (btrfs, zfs) — same honest-limits framing as Verify/Recovery's own
caveats. Scope: files only, not recursive folder-shredding (a natural Phase 7 candidate).

## Cross-cutting

- **Versioning** per project policy (bump `breaknwipe/__init__.py` + `pyproject.toml`, changelog,
  README badge): Phase 1 → v3.0.0; Phases 2–4 → subsequent minors.
- **Safety** carries the fsck-established model into every new destructive surface: validated
  block-device paths, never auto-unmount, refuse offline ops on mounted filesystems, system-disk +
  typed-confirmation gates, exact-command previews, restore-to-a-different-device enforcement.
- **Verification** is end-to-end against disposable loopback devices (the pattern already used for
  fsck), never on a real disk until loopback passes — full details in each phase's plan.
