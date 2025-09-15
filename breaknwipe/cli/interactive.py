"""
Interactive Mode for BreakNWipe CLI

Provides an interactive interface for device selection and wiping operations.
"""

import sys
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from ..device import DeviceDetector
from ..wipe_engine import WipeEngine, AlgorithmType
from ..certificate import CertificateGenerator

console = Console()


class InteractiveMode:
    """Interactive mode for guided device wiping operations."""

    def __init__(self):
        """Initialize interactive mode."""
        self.detector = DeviceDetector()
        self.engine = WipeEngine()
        self.cert_generator = CertificateGenerator()

    def run(self):
        """Run the interactive mode."""
        console.print("\n[bold blue]Welcome to BreakNWipe Interactive Mode![/bold blue]")
        console.print("This mode will guide you through the secure wiping process.\n")

        # List available devices
        devices = self.detector.list_devices()

        if not devices:
            console.print("[red]No storage devices found![/red]")
            console.print("Please ensure devices are connected and try again.")
            return

        console.print(f"[blue]Found {len(devices)} storage device(s):[/blue]\n")

        for i, device in enumerate(devices, 1):
            status = "Mounted" if device.is_mounted else "Available"
            warning = " ⚠️" if device.is_mounted else ""
            console.print(f"  {i}. [green]{device.path}[/green] - {device.model} "
                         f"({device.capacity_human}) [{status}]{warning}")

        # Device selection
        while True:
            try:
                choice = Prompt.ask("\nSelect device to wipe", default="1")
                device_idx = int(choice) - 1

                if 0 <= device_idx < len(devices):
                    selected_device = devices[device_idx]
                    break
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")

        # Confirm device selection
        console.print(f"\n[bold yellow]WARNING:[/bold yellow] You selected: {selected_device.path}")
        console.print(f"Model: {selected_device.model}")
        console.print(f"Capacity: {selected_device.capacity_human}")
        console.print("[red]ALL DATA ON THIS DEVICE WILL BE PERMANENTLY DESTROYED![/red]")

        if not Confirm.ask("Are you sure you want to continue?", default=False):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Algorithm selection
        algorithms = [
            ("nist-clear", "NIST SP 800-88 Clear (1 pass) - Fast"),
            ("nist-purge", "NIST SP 800-88 Purge (3 passes) - Standard"),
            ("dod-3pass", "DoD 5220.22-M (3 passes) - Government"),
            ("dod-7pass", "DoD 5220.22-M (7 passes) - High Security"),
            ("zeros", "Zero-fill (1 pass) - Quick wipe"),
        ]

        console.print("\n[blue]Available algorithms:[/blue]")
        for i, (algo, desc) in enumerate(algorithms, 1):
            console.print(f"  {i}. {algo} - {desc}")

        while True:
            try:
                choice = Prompt.ask("\nSelect wiping algorithm", default="2")
                algo_idx = int(choice) - 1

                if 0 <= algo_idx < len(algorithms):
                    selected_algo = algorithms[algo_idx][0]
                    break
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")

        # Additional options
        verify = Confirm.ask("Verify wipe completion?", default=True)
        generate_cert = Confirm.ask("Generate wipe certificate?", default=True)

        # Execute wipe
        console.print(f"\n[green]Starting wipe operation...[/green]")
        console.print(f"Device: {selected_device.path}")
        console.print(f"Algorithm: {selected_algo}")
        console.print(f"Verify: {'Yes' if verify else 'No'}")
        console.print(f"Certificate: {'Yes' if generate_cert else 'No'}")

        try:
            # This is a simplified version - in a real implementation,
            # you'd want proper progress tracking and error handling
            result = self.engine.wipe_device(
                device_path=selected_device.path,
                algorithm=AlgorithmType(selected_algo),
                verify=verify
            )

            if result.success:
                console.print("[green]✓ Wipe operation completed successfully![/green]")

                if generate_cert:
                    # Generate certificate
                    cert_data = {
                        "device": selected_device.path,
                        "algorithm": selected_algo,
                        "timestamp": result.timestamp.isoformat(),
                        "success": True
                    }

                    cert_file = self.cert_generator.generate_certificate(cert_data)
                    console.print(f"[green]✓ Certificate generated: {cert_file}[/green]")
            else:
                console.print(f"[red]✗ Wipe operation failed: {result.error_message}[/red]")

        except Exception as e:
            console.print(f"[red]Error during wipe operation: {e}[/red]")