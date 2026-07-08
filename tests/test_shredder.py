#!/usr/bin/env python3
"""
Test script for the file shredder module (breaknwipe.device.shredder).

Covers the security-sensitive paths in isolation, without needing root or a
real block device: overwrite-then-delete mechanics, path-traversal refusal,
symlink refusal (both same-mount and mount-escaping), directory listing
containment, and the reliability assessment's shape.
"""

import os
import sys
import tempfile
import shutil
import threading
from pathlib import Path
from unittest import mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from breaknwipe.device import shredder  # noqa: E402


def with_mount(mount_point):
    """Patch get_mount_point so the module believes `mount_point` is a
    mounted filesystem for any partition string used in these tests."""
    return mock.patch("breaknwipe.device.shredder.get_mount_point", return_value=mount_point)


def test_overwrite_and_delete():
    print("\n🔨 Testing overwrite + delete of a regular file...")
    d = tempfile.mkdtemp()
    try:
        f = os.path.join(d, "secret.txt")
        original = b"THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG" * 500
        with open(f, "wb") as fh:
            fh.write(original)

        events = []
        with with_mount(d):
            result = shredder.shred_files(
                partition="/dev/fake0", paths=[f], algorithm="dod-3pass",
                progress_callback=lambda p: events.append(p),
            )

        if result.shredded != 1 or result.failed != 0:
            print(f"❌ Expected 1 shredded/0 failed, got shredded={result.shredded} failed={result.failed}")
            return False
        if os.path.exists(f):
            print("❌ File still exists after shredding")
            return False
        if not events:
            print("❌ No progress events were emitted")
            return False
        outcome = result.files[0]
        if outcome.passes_completed != 3:
            print(f"❌ Expected 3 passes completed (dod-3pass), got {outcome.passes_completed}")
            return False

        print(f"✅ File overwritten across {outcome.passes_completed} passes, "
              f"{len(events)} progress events, and removed")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_empty_file():
    print("\n🔨 Testing shredding a zero-byte file...")
    d = tempfile.mkdtemp()
    try:
        f = os.path.join(d, "empty.bin")
        open(f, "wb").close()
        with with_mount(d):
            result = shredder.shred_files(partition="/dev/fake0", paths=[f], algorithm="random")
        if result.shredded != 1 or os.path.exists(f):
            print(f"❌ Empty file wasn't cleanly shredded: {result.to_dict()}")
            return False
        print("✅ Zero-byte file handled correctly")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_path_traversal_refused():
    print("\n🔒 Testing path-traversal escape is refused...")
    d = tempfile.mkdtemp()
    try:
        with with_mount(d):
            result = shredder.shred_files(partition="/dev/fake0", paths=["/etc/passwd"], algorithm="zeros")
        outcome = result.files[0]
        if outcome.success or "outside" not in (outcome.error or "").lower():
            print(f"❌ Traversal was not refused: {outcome.to_dict()}")
            return False
        if not os.path.exists("/etc/passwd"):
            print("❌ CRITICAL: /etc/passwd is gone!")
            return False

        try:
            shredder.list_directory("/dev/fake0", "../../etc")
            print("❌ Directory-listing traversal was NOT refused")
            return False
        except ValueError:
            pass

        print("✅ Path traversal correctly refused for both shred and browse")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_symlink_refused():
    print("\n🔒 Testing symlinks are refused (same-mount and mount-escaping)...")
    d = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    try:
        target = os.path.join(d, "target.txt")
        with open(target, "w") as fh:
            fh.write("data")
        link = os.path.join(d, "link.txt")
        os.symlink(target, link)

        outside_file = os.path.join(outside, "sensitive.txt")
        with open(outside_file, "w") as fh:
            fh.write("sensitive")
        escape_link = os.path.join(d, "escape.txt")
        os.symlink(outside_file, escape_link)

        with with_mount(d):
            result = shredder.shred_files(partition="/dev/fake0", paths=[link, escape_link], algorithm="zeros")

        ok = True
        for outcome in result.files:
            if outcome.success or "symlink" not in (outcome.error or "").lower():
                print(f"❌ Symlink was not refused: {outcome.to_dict()}")
                ok = False

        if not os.path.exists(target):
            print("❌ CRITICAL: symlink target inside mount was shredded")
            ok = False
        if open(outside_file).read() != "sensitive":
            print("❌ CRITICAL: symlink target outside mount was modified")
            ok = False

        if ok:
            print("✅ Both symlink cases correctly refused; targets untouched")
        return ok
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)


def test_hardlink_warning():
    print("\n⚠️  Testing hardlink warning is surfaced (not a refusal)...")
    d = tempfile.mkdtemp()
    try:
        f1 = os.path.join(d, "a.txt")
        with open(f1, "w") as fh:
            fh.write("x" * 10)
        f2 = os.path.join(d, "b.txt")
        os.link(f1, f2)

        with with_mount(d):
            result = shredder.shred_files(partition="/dev/fake0", paths=[f1], algorithm="zeros")

        outcome = result.files[0]
        if not outcome.success or not outcome.warnings:
            print(f"❌ Expected success with a hardlink warning: {outcome.to_dict()}")
            return False
        print(f"✅ Hardlink warning surfaced: {outcome.warnings[0]}")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_list_directory():
    print("\n📂 Testing directory listing...")
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, "sub"))
        open(os.path.join(d, "file.txt"), "w").close()

        with with_mount(d):
            listing = shredder.list_directory("/dev/fake0", "")
            names = sorted(e.name for e in listing.entries)
            if names != ["file.txt", "sub"]:
                print(f"❌ Unexpected listing: {names}")
                return False

            sub_listing = shredder.list_directory("/dev/fake0", "sub")
            if sub_listing.parent is None:
                print("❌ Subdirectory listing should have a parent")
                return False

        print("✅ Directory listing (root + subdirectory + parent linkage) correct")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_mid_file_cancellation():
    print("\n🛑 Testing cancellation mid-file is reported as cancelled, not failed...")
    d = tempfile.mkdtemp()
    try:
        f = os.path.join(d, "big.bin")
        with open(f, "wb") as fh:
            fh.write(os.urandom(20_000_000))

        cancel_event = threading.Event()

        def on_progress(payload):
            # Cancel partway through the first pass -- regression test for a
            # bug where mid-file cancellation was reported as job status
            # "failed" instead of "cancelled" (the top-level `cancelled` flag
            # was only set by the loop's between-files check, never by a
            # cancellation that landed inside _overwrite_file itself).
            if payload.get("current_pass") == 1 and payload.get("bytes_written", 0) > 1_000_000:
                cancel_event.set()

        with with_mount(d):
            result = shredder.shred_files(
                partition="/dev/fake0", paths=[f], algorithm="gutmann",
                progress_callback=on_progress, cancel_event=cancel_event,
            )

        if not result.cancelled:
            print(f"❌ Expected result.cancelled=True, got {result.to_dict()}")
            return False
        if result.failed != 0:
            print(f"❌ A user cancellation should not count as a failure, got failed={result.failed}")
            return False
        if not os.path.exists(f):
            print("❌ File should still exist -- it was not fully shredded before cancellation")
            return False

        print("✅ Mid-file cancellation correctly reported as cancelled (not failed); file left in place")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_reliability_assessment_shape():
    print("\n📋 Testing assess_reliability() return shape...")
    result = shredder.assess_reliability("/dev/nonexistent-fake-partition")
    required = {"partition", "fstype", "rotational", "reliable", "warnings"}
    if not required.issubset(result.keys()):
        print(f"❌ Missing keys in reliability result: {required - result.keys()}")
        return False
    if not isinstance(result["reliable"], bool) or not isinstance(result["warnings"], list):
        print(f"❌ Unexpected types in reliability result: {result}")
        return False
    print(f"✅ Reliability assessment shape correct: {result}")
    return True


def main():
    print("🔧 File Shredder Module Test")
    print("=" * 40)

    tests = [
        test_overwrite_and_delete,
        test_empty_file,
        test_path_traversal_refused,
        test_symlink_refused,
        test_hardlink_warning,
        test_mid_file_cancellation,
        test_list_directory,
        test_reliability_assessment_shape,
    ]

    results = [t() for t in tests]
    passed = sum(results)
    total = len(results)

    print(f"\n📊 Test Summary: {passed}/{total} passed")
    if passed == total:
        print("🎉 All shredder tests passed!")
    else:
        print("⚠️  Some shredder tests failed.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
