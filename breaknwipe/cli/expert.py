"""
Expert Mode for BreakNWipe CLI

Provides direct command-line access to wiping operations for advanced users.
"""

import sys
from pathlib import Path
from typing import Optional
from rich.console import Console

from ..device import DeviceDetector, DeviceHandler
from ..wipe_engine import WipeEngine, AlgorithmType
from ..certificate import CertificateGenerator

console = Console()


class ExpertMode:
    """Expert mode for direct wiping operations."""

    def __init__(self):
        """Initialize expert mode."""
        self.detector = DeviceDetector()
        self.handler = DeviceHandler()
        self.engine = WipeEngine()
        self.cert_generator = CertificateGenerator()

    def run_wipe(self, device: str, algorithm: str, passes: Optional[int] = None,
                 verify: bool = False, generate_certificate: bool = False,
                 output_dir: Optional[str] = None, force: bool = False,
                 dry_run: bool = False):
        """Execute wipe operation with specified parameters."""

        console.print(f"[blue]Expert Mode - Wiping device:[/blue] {device}")
        console.print(f"Algorithm: {algorithm}")
        if passes:
            console.print(f"Passes: {passes}")
        console.print(f"Verify: {verify}")
        console.print(f"Certificate: {generate_certificate}")
        console.print(f"Dry run: {dry_run}")
        console.print()

        # Validate device exists
        try:
            device_info = self.detector.get_device_info(device)
            console.print(f"Device: {device_info.model} ({device_info.capacity_human})")
        except Exception as e:
            console.print(f"[red]Error accessing device {device}: {e}[/red]")
            if not force:
                return

        # Safety check
        if not force and not dry_run:
            console.print("[red]SAFETY WARNING:[/red]")
            console.print(f"You are about to wipe device: {device}")
            console.print("[red]ALL DATA WILL BE PERMANENTLY DESTROYED![/red]")
            console.print()
            console.print("Use --force to skip this warning.")
            console.print("Use --dry-run to simulate without actual wiping.")
            return

        if dry_run:
            console.print("[yellow]DRY RUN MODE - No actual wiping will be performed[/yellow]")

        try:
            # Convert algorithm string to AlgorithmType
            algo_type = AlgorithmType(algorithm)

            # Execute wipe
            result = self.engine.wipe_device(
                device_path=device,
                algorithm=algo_type,
                verify=verify,
                dry_run=dry_run
            )

            if result.success:
                console.print("[green]✓ Wipe operation completed successfully![/green]")

                if generate_certificate and not dry_run:
                    # Generate certificate
                    cert_data = {
                        "device": device,
                        "algorithm": algorithm,
                        "passes": passes,
                        "verify": verify,
                        "timestamp": result.timestamp.isoformat(),
                        "success": True
                    }

                    if output_dir:
                        output_path = Path(output_dir)
                        output_path.mkdir(parents=True, exist_ok=True)
                        cert_file = self.cert_generator.generate_certificate(
                            cert_data, output_path
                        )
                    else:
                        cert_file = self.cert_generator.generate_certificate(cert_data)

                    console.print(f"[green]✓ Certificate generated: {cert_file}[/green]")
            else:
                console.print(f"[red]✗ Wipe operation failed: {result.error_message}[/red]")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Error during wipe operation: {e}[/red]")
            sys.exit(1)