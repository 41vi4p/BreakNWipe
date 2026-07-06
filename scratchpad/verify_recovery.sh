#!/usr/bin/env bash
# Loopback verification for BreakNWipe deleted-file recovery (Phase 4).
#
# Proves, on disposable loop devices (no real disk touched):
#   1. NTFS: create files -> delete -> scan_deleted finds them WITH names ->
#      recover_files to a DIFFERENT device -> byte-identical (md5 match).
#   2. Recovery REFUSES to write back to the source device.
#   3. Deep scan (photorec) carves file contents from an ext4 image.
#   4. After a full zero-wipe, scan reports nothing recoverable (honesty check).
#
# Run:  sudo bash scratchpad/verify_recovery.sh
# Needs: sleuthkit, testdisk, ntfs-3g, mkfs.ntfs  (sudo apt install -y sleuthkit testdisk ntfs-3g)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'set +e; for m in "$WORK"/mnt_*; do umount "$m" 2>/dev/null; done; for l in $(cat "$WORK"/loops 2>/dev/null); do losetup -d "$l" 2>/dev/null; done; rm -rf "$WORK"' EXIT
touch "$WORK/loops"

say() { printf "\n\033[1;34m== %s\033[0m\n" "$*"; }
pass() { printf "\033[1;32mPASS\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31mFAIL\033[0m %s\n" "$*"; exit 1; }

mkloop() {  # $1 = size (e.g. 64M) -> prints loop dev
  local img="$WORK/img_$RANDOM.bin"
  dd if=/dev/zero of="$img" bs=1M count="${1%M}" status=none
  local dev; dev="$(losetup --show -f "$img")"
  echo "$dev" >> "$WORK/loops"
  echo "$dev"
}

run_py() { (cd "$REPO" && uv run python -c "$1"); }

# ---------------------------------------------------------------- NTFS undelete
say "1. NTFS undelete with filenames (fls/icat)"
NTFS="$(mkloop 96M)"
mkfs.ntfs -F -q "$NTFS" >/dev/null 2>&1
MNT="$WORK/mnt_ntfs"; mkdir -p "$MNT"
mount "$NTFS" "$MNT"
echo "hello recovery world $(date)" > "$MNT/report.txt"
head -c 40000 /dev/urandom | base64 > "$MNT/notes.md"
sync
MD5_REPORT="$(md5sum "$MNT/report.txt" | cut -d' ' -f1)"
MD5_NOTES="$(md5sum "$MNT/notes.md" | cut -d' ' -f1)"
rm -f "$MNT/report.txt" "$MNT/notes.md"
sync
umount "$MNT"

OUT="$WORK/recovered"; mkdir -p "$OUT"   # on the host fs = a different device
run_py "
from breaknwipe.device.recovery import scan_deleted, recover_files
s = scan_deleted('$NTFS')
assert not s.refused, s.refusal_reason
names = {f.name: f.inode for f in s.files}
print('found:', sorted(names))
assert 'report.txt' in names, 'report.txt not listed by scan'
assert 'notes.md' in names, 'notes.md not listed by scan'
r = recover_files('$NTFS', [names['report.txt'], names['notes.md']], '$OUT')
assert not r.refused, r.refusal_reason
assert r.recovered == 2, r.to_dict()
print('recovered files:', r.recovered_files)
"
# Match recovered bytes against the pre-delete md5s.
GOT_REPORT=""; GOT_NOTES=""
for f in "$OUT"/recovered_*; do
  m="$(md5sum "$f" | cut -d' ' -f1)"
  [ "$m" = "$MD5_REPORT" ] && GOT_REPORT=1
  [ "$m" = "$MD5_NOTES" ] && GOT_NOTES=1
done
[ -n "$GOT_REPORT" ] && [ -n "$GOT_NOTES" ] && pass "recovered files byte-identical (md5 match)" \
  || fail "recovered content did not match original md5"

# ------------------------------------------------------- same-device refusal
say "2. Refuse recovering onto the source device"
SRCMNT="$WORK/mnt_src"; mkdir -p "$SRCMNT"
mount "$NTFS" "$SRCMNT"
mkdir -p "$SRCMNT/out_here"
run_py "
from breaknwipe.device.recovery import recover_files
r = recover_files('$NTFS', ['64'], '$SRCMNT/out_here')
assert r.refused, 'should have refused same-device recovery: ' + str(r.to_dict())
print('refusal_reason:', r.refusal_reason)
"
umount "$SRCMNT"
pass "recovery refuses same-device output"

# ------------------------------------------------------------- ext4 deep carve
say "3. Deep carve (photorec) on ext4"
EXT="$(mkloop 96M)"
mkfs.ext4 -q -F "$EXT" >/dev/null 2>&1
EMNT="$WORK/mnt_ext"; mkdir -p "$EMNT"
mount "$EXT" "$EMNT"
# A JPEG-signatured file photorec can carve by magic bytes.
printf '\xff\xd8\xff\xe0\x00\x10JFIF' > "$EMNT/photo.jpg"
head -c 20000 /dev/urandom >> "$EMNT/photo.jpg"
printf '\xff\xd9' >> "$EMNT/photo.jpg"
sync
rm -f "$EMNT/photo.jpg"; sync
umount "$EMNT"
CARVE="$WORK/carved"; mkdir -p "$CARVE"
run_py "
from breaknwipe.device.recovery import deep_scan_recover
r = deep_scan_recover('$EXT', '$CARVE')
assert not r.refused, r.refusal_reason
print('carved:', r.recovered, r.error)
assert r.recovered >= 1, 'photorec carved nothing: ' + str(r.to_dict())
"
pass "photorec carved >=1 file from ext4"

# ------------------------------------------------------------ honesty check
say "4. After a full zero-wipe, nothing recoverable"
dd if=/dev/zero of="$NTFS" bs=1M status=none
sync
run_py "
from breaknwipe.device.recovery import scan_deleted
s = scan_deleted('$NTFS')
named = [f for f in s.files if not f.name.startswith('\$') and f.name]
print('post-wipe named files:', [f.name for f in named])
assert not named, 'wiped device still lists recoverable named files!'
"
pass "wiped device reports nothing recoverable (honesty check)"

say "ALL RECOVERY CHECKS PASSED"
