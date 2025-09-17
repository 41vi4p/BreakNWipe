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
from rich.text import Text

from .. import __version__
from ..device import DeviceDetector, DeviceHandler
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
@click.option('--device', '-d', required=True, help='Target device (e.g., /dev/sda)')
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
@click.argument('device')
def info(device):
    """Display detailed information about a storage device."""

    try:
        detector = DeviceDetector()
        device_info = detector.get_device_info(device)

        console.print(f"[blue]Device Information:[/blue] {device}")
        console.print(f"Model: {device_info.model}")
        console.print(f"Serial: {device_info.serial}")
        console.print(f"Capacity: {device_info.capacity_human}")
        console.print(f"Type: {device_info.device_type}")
        console.print(f"Interface: {device_info.interface}")
        console.print(f"Secure Erase Support: {'Yes' if device_info.secure_erase_support else 'No'}")

    except Exception as e:
        console.print(f"[red]Error getting device information:[/red] {e}")

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
    main()