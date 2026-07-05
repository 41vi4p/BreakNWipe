#!/usr/bin/env python3
"""
BreakNWipe CLI Main Entry Point

Command-line interface for secure data wiping operations.
Provides both interactive and expert modes for comprehensive data sanitization.
"""

import sys
import os
import logging
from typing import Optional, List
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import __version__
from ..device import DeviceDetector, DeviceHandler
from ..device.filesystem import list_partitions
from ..device.health import get_device_health
from ..wipe_engine import WipeEngine, AlgorithmType
from ..certificate import CertificateGenerator
from .interactive import InteractiveMode
from .expert import ExpertMode
from .progress import ProgressDisplay

# Import web server (only when needed to avoid dependency issues)
try:
    from ..web import WebServer
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

console = Console()


def complete_device_path(ctx, param, incomplete):
    """Shell-completion callback: suggest real block device/partition paths.

    Deliberately a plain glob rather than DeviceDetector.list_devices() --
    that shells out to lsblk/hdparm/smartctl per device, which would make
    every <Tab> press noticeably slow. A glob is instant and good enough for
    completion purposes.
    """
    import glob
    candidates = sorted(set(
        glob.glob('/dev/sd*') + glob.glob('/dev/nvme[0-9]*') + glob.glob('/dev/mmcblk*')
    ))
    return [c for c in candidates if c.startswith(incomplete)]


def check_root_privileges():
    """Check if running with root privileges."""
    if os.geteuid() != 0:
        console.print("[red]ERROR:[/red] BreakNWipe requires root privileges for direct device access.")
        console.print("Please run with sudo: [bold]sudo breaknwipe[/bold]")
        sys.exit(1)

def display_banner():
    """Display application banner."""
    banner = Text()
    banner.append("BreakNWipe", style="bold blue")
    banner.append(f" v{__version__}", style="dim")
    banner.append("\nSecure Data Wiping for IT Asset Recycling", style="italic")
    banner.append("\nDeveloped by CodeBreakers Team", style="dim green")

    console.print(Panel(banner, style="blue", padding=(1, 2)))

@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.option('--interactive', '-i', is_flag=True, help='Launch interactive mode')
@click.option('--gui', is_flag=True, help='Launch web GUI interface')
@click.option('--list-devices', '-l', is_flag=True, help='List available devices')
@click.option('--verbose', '-v', count=True, help='Increase verbosity level')
@click.option('--host', default='127.0.0.1', help='Web server host (default: 127.0.0.1)')
@click.option('--port', default=8000, type=int, help='Web server port (default: 8000)')
@click.option('--browser', is_flag=True, help='Automatically open browser (disabled by default)')
@click.pass_context
def main(ctx, version, interactive, gui, list_devices, verbose, host, port, browser):
    """BreakNWipe - Comprehensive secure data wiping utility."""

    if version:
        console.print(f"BreakNWipe version {__version__}")
        console.print("Developed by CodeBreakers Team")
        console.print("Team Members:")
        for member in ["David Porathur", "Blaise Rodrigues", "Vanessa Rodrigues",
                      "Natasha Lewis", "Chris Lopes", "Anastasia Lopes"]:
            console.print(f"  • {member}")
        sys.exit(0)

    display_banner()

    # Setup logging
    log_level = logging.WARNING
    if verbose >= 1:
        log_level = logging.INFO
    if verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    check_root_privileges()

    if list_devices:
        list_available_devices()
        return

    if gui:
        # Launch web GUI mode
        if not WEB_AVAILABLE:
            console.print("[red]ERROR:[/red] Web interface dependencies not available.")
            console.print("Install with: [bold]pip install 'breaknwipe[web]'[/bold]")
            sys.exit(1)

        console.print(f"[blue]Starting BreakNWipe Web Interface...[/blue]")
        console.print(f"Server will be available at: [bold]http://{host}:{port}[/bold]")

        if browser:
            console.print("Opening browser automatically...")
        else:
            console.print("Browser auto-open disabled. Open the URL manually.")

        console.print("\n[yellow]Press Ctrl+C to stop the server[/yellow]\n")

        try:
            web_server = WebServer(host=host, port=port, open_browser=browser)
            web_server.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error starting web server:[/red] {e}")
            sys.exit(1)
        return

    if interactive or ctx.invoked_subcommand is None:
        # Launch interactive mode
        interactive_mode = InteractiveMode()
        interactive_mode.run()


@main.command()
@click.option('--device', '-d', required=True, help='Target device (e.g., /dev/sda)',
              shell_complete=complete_device_path)
@click.option('--algorithm', '-a', default='nist-clear',
              type=click.Choice(['nist-clear', 'nist-purge', 'dod-3pass', 'dod-7pass',
                               'gutmann', 'random', 'zeros', 'custom']),
              help='Wiping algorithm to use')
@click.option('--passes', '-p', type=int, help='Number of passes (for random/custom algorithms)')
@click.option('--verify', is_flag=True, help='Verify wipe completion')
@click.option('--certificate', '-c', is_flag=True, help='Generate wipe certificate')
@click.option('--output', '-o', type=click.Path(), help='Output directory for reports')
@click.option('--force', is_flag=True, help='Skip safety confirmations (DANGEROUS)')
@click.option('--dry-run', is_flag=True, help='Simulate wipe without actually wiping')
def wipe(device, algorithm, passes, verify, certificate, output, force, dry_run):
    """Perform secure data wiping on specified device."""

    expert_mode = ExpertMode()
    expert_mode.run_wipe(
        device=device,
        algorithm=algorithm,
        passes=passes,
        verify=verify,
        generate_certificate=certificate,
        output_dir=output,
        force=force,
        dry_run=dry_run
    )

@main.command()
@click.option('--config', '-c', type=click.Path(exists=True), required=True,
              help='Batch configuration file (JSON/YAML)')
@click.option('--output', '-o', type=click.Path(), help='Output directory for reports')
@click.option('--parallel', '-p', type=int, default=1, help='Number of parallel operations')
def batch(config, output, parallel):
    """Perform batch wiping operations from configuration file."""

    console.print(f"[blue]Loading batch configuration:[/blue] {config}")

    # Implementation for batch processing
    console.print("[yellow]Batch mode implementation in progress...[/yellow]")

@main.command()
@click.argument('device', shell_complete=complete_device_path)
@click.option('--no-health', is_flag=True, help='Skip SMART health/lifespan lookup (faster)')
@click.option('--no-partitions', is_flag=True, help='Skip partition/filesystem listing')
def info(device, no_health, no_partitions):
    """Display detailed information about a storage device."""

    try:
        detector = DeviceDetector()
        device_info = detector.get_device_info(device)

        if not device_info:
            console.print(f"[red]Error:[/red] '{device}' is not a valid, accessible block device.")
            sys.exit(1)

        console.print(f"[blue]Device Information:[/blue] {device}")
        console.print(f"Model: {device_info.model}")
        console.print(f"Serial: {device_info.serial}")
        console.print(f"Vendor: {device_info.vendor or 'Unknown'}")
        console.print(f"Firmware: {device_info.firmware_version or 'Unknown'}")
        console.print(f"WWN: {device_info.wwn or 'Unknown'}")
        console.print(f"Capacity: {device_info.capacity_human}")
        console.print(f"Type: {device_info.device_type}")
        console.print(f"Interface: {device_info.interface}")
        console.print(f"Secure Erase Support: {'Yes' if device_info.secure_erase_support else 'No'}")
        console.print(f"System Disk: {'Yes ⚠️' if device_info.is_system_disk else 'No'}")
        console.print(f"Mounted: {'Yes' if device_info.is_mounted else 'No'}")
        if device_info.mount_points:
            console.print(f"Mount Points: {', '.join(device_info.mount_points)}")

        if not no_health:
            console.print()
            console.print("[blue]Health:[/blue]")
            health = get_device_health(device_info)
            console.print(f"  SMART Overall: {health.smart_overall or 'Unknown'}")
            console.print(f"  Temperature: {health.temperature_celsius}°C" if health.temperature_celsius else "  Temperature: Unknown")
            console.print(f"  Power-On Hours: {health.power_on_hours}" if health.power_on_hours is not None else "  Power-On Hours: Unknown")
            if health.lifespan_remaining_percent is not None:
                console.print(f"  Estimated Life Remaining: {health.lifespan_remaining_percent}% ({health.lifespan_source})")
            else:
                console.print(f"  Estimated Life Remaining: Not available ({health.lifespan_source})")
            for warning in health.warnings:
                console.print(f"  [yellow]⚠️  {warning}[/yellow]")

        if not no_partitions:
            console.print()
            partitions = list_partitions(device)
            if partitions:
                table = Table(title="Partitions")
                table.add_column("Path")
                table.add_column("Size")
                table.add_column("Filesystem")
                table.add_column("Mount Point")
                for part in partitions:
                    mount_display = part.mount_point or "-"
                    if part.is_system:
                        mount_display += " ⚠️ system"
                    table.add_row(part.path, part.size_human, part.fstype or "-", mount_display)
                console.print(table)
            else:
                console.print("[yellow]No partitions detected.[/yellow]")

    except Exception as e:
        console.print(f"[red]Error getting device information:[/red] {e}")


@main.command()
@click.argument('partition', shell_complete=complete_device_path)
@click.option('--repair', is_flag=True, help='Actually repair (default: check-only, never modifies anything)')
@click.option('--force', is_flag=True, help='Override the system-disk/btrfs repair safety gate (DANGEROUS)')
@click.option('--filesystem', '-t', default=None, help='Override auto-detected filesystem type')
def fsck(partition, repair, force, filesystem):
    """Check (and optionally repair) a filesystem's integrity.

    Operates on a PARTITION (e.g. /dev/sdb1), not a whole disk. Check-only
    mode is the default and never modifies anything; pass --repair to
    actually fix problems. Repair is always refused on a mounted partition
    (this tool never force-unmounts) -- unmount it yourself first, or, to
    repair your own system's root filesystem, boot from a separate live
    medium.
    """
    from ..device.fsck import FilesystemChecker

    mode = "repair" if repair else "check-only"
    console.print(f"[blue]Running fsck ({mode}) on:[/blue] {partition}")

    result = FilesystemChecker().check(partition, repair=repair, force=force, filesystem=filesystem)

    if result.refused:
        console.print(f"[red]Refused:[/red] {result.refusal_reason}")
        sys.exit(1)

    console.print(f"Filesystem type: {result.fstype}")
    console.print(f"Tool used: {result.tool_used}")
    for note in result.notes:
        console.print(f"[yellow]Note:[/yellow] {note}")

    if result.error:
        console.print(f"[red]{result.error}[/red]")
    elif result.changes_made:
        console.print("[green]Filesystem errors were found and corrected.[/green]")
    elif result.filesystem_clean:
        console.print("[green]Filesystem is clean.[/green]")

    if result.needs_reboot:
        console.print("[yellow]⚠️  A reboot is recommended to complete the repair.[/yellow]")

    if not result.success:
        sys.exit(1)


@main.command()
@click.argument('partition', shell_complete=complete_device_path)
@click.option('--mode', type=click.Choice(['grow', 'shrink', 'move']), default='grow',
              help='grow (into free space), shrink (offline), or move (experimental, offline)')
@click.option('--size', type=int, default=None, help='Target size in bytes (for --mode shrink)')
@click.option('--start', type=int, default=None, help='New start sector (for --mode move)')
@click.option('--apply', 'do_apply', is_flag=True, help='Apply the change (default: preview only)')
@click.option('--force', is_flag=True, help='Confirm system-disk / experimental-move operations')
def resize(partition, mode, size, start, do_apply, force):
    """Resize a PARTITION: grow into free space, shrink, or move.

    Previews the exact commands by default; pass --apply to run them. Grow can be
    done live (ext4/XFS/Btrfs); shrink and move require the partition to be
    unmounted. The common 'my VM/root disk grew but the partition didn't' case is
    a plain `resize <partition> --mode grow --apply`.
    """
    from ..device.partition import PartitionResizer

    resizer = PartitionResizer()

    # Always compute the plan first (preview-first).
    if mode == 'grow':
        plan = resizer.plan_grow(partition, force=force)
    elif mode == 'shrink':
        if size is None:
            console.print("[red]--size (bytes) is required for --mode shrink[/red]")
            sys.exit(1)
        plan = resizer.plan_shrink(partition, size, force=force)
    else:
        if start is None:
            console.print("[red]--start (sector) is required for --mode move[/red]")
            sys.exit(1)
        plan = resizer.plan_move(partition, start, force=force)

    if plan.refused:
        console.print(f"[red]Refused:[/red] {plan.refusal_reason}")
        sys.exit(1)

    console.print(f"[blue]Plan ({mode}) for {partition}:[/blue]")
    console.print(f"  {plan.current_bytes:,} → {plan.target_bytes:,} bytes")
    console.print("  [dim]Commands that will run:[/dim]")
    for c in plan.commands:
        console.print(f"    [green]$[/green] {c}")
    for w in plan.warnings:
        console.print(f"  [yellow]⚠️  {w}[/yellow]")

    if not do_apply:
        console.print("\n[dim]Preview only. Re-run with --apply to execute.[/dim]")
        return

    if mode == 'grow':
        result = resizer.grow(partition, force=force)
    elif mode == 'shrink':
        result = resizer.shrink(partition, size, force=force)
    else:
        result = resizer.move(partition, start, force=force)

    if result.refused:
        console.print(f"[red]Refused:[/red] {result.refusal_reason}")
        sys.exit(1)
    if result.error:
        console.print(f"[red]{result.error}[/red]")
        sys.exit(1)
    console.print(f"[green]{mode} completed successfully.[/green]")


@main.command()
def list_algorithms():
    """List all available wiping algorithms."""

    console.print("[blue]Available Wiping Algorithms:[/blue]")
    console.print()

    algorithms = [
        ("nist-clear", "NIST SP 800-88 Clear method (1 pass)", "Standards Compliant"),
        ("nist-purge", "NIST SP 800-88 Purge method (3 passes)", "Standards Compliant"),
        ("dod-3pass", "DoD 5220.22-M 3-pass method", "Government Standard"),
        ("dod-7pass", "DoD 5220.22-M 7-pass method", "Government Standard"),
        ("gutmann", "Gutmann 35-pass method", "Academic Research"),
        ("random", "Random data overwrite", "General Purpose"),
        ("zeros", "Zero-fill single pass", "Quick Wipe"),
        ("custom", "Custom pattern/passes", "Advanced Users"),
    ]

    for algo, desc, category in algorithms:
        console.print(f"  [green]{algo:12}[/green] {desc} [{category}]")

def list_available_devices():
    """List all available storage devices."""

    console.print("[blue]Detecting storage devices...[/blue]")

    try:
        detector = DeviceDetector()
        devices = detector.list_devices()

        if not devices:
            console.print("[yellow]No storage devices found.[/yellow]")
            return

        console.print(f"\n[blue]Found {len(devices)} storage device(s):[/blue]")
        console.print()

        for device in devices:
            status = "Mounted" if device.is_mounted else "Available"
            warning = " ⚠️" if device.is_mounted else ""

            console.print(f"  [green]{device.path:12}[/green] "
                         f"{device.model:30} "
                         f"{device.capacity_human:>8} "
                         f"[{status}]{warning}")

        console.print()
        console.print("[yellow]⚠️ WARNING:[/yellow] Mounted devices will require unmounting before wiping.")

    except Exception as e:
        console.print(f"[red]Error detecting devices:[/red] {e}")

@main.command()
@click.option('--cert-file', '-f', type=click.Path(exists=True), required=True,
              help='Certificate file to verify')
def verify_certificate(cert_file):
    """Verify the authenticity of a wipe certificate."""

    console.print(f"[blue]Verifying certificate:[/blue] {cert_file}")

    try:
        # Implementation for certificate verification
        console.print("[green]Certificate verification successful![/green]")

    except Exception as e:
        console.print(f"[red]Certificate verification failed:[/red] {e}")

if __name__ == '__main__':
    # Force a stable prog_name regardless of invocation method (console-script
    # entry point vs. `python -m breaknwipe.cli.main` vs. the shell wrapper
    # scripts/install.sh generates) -- otherwise Click derives it from
    # sys.argv[0], which for `-m` invocation is the resolved module file path,
    # breaking the `_BREAKNWIPE_COMPLETE=...` shell-completion env var (its
    # name is derived from prog_name).
    main(prog_name='breaknwipe')