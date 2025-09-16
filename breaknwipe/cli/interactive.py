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
from ..wipe_engine import WipeEngine, AlgorithmType, create_algorithm
from ..certificate import CertificateGenerator
from ..certificate.report import WipeReport, DeviceInfo, WipePassResult, VerificationResult
from .progress import WipeProgressDisplay

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
            # Create algorithm instance
            algorithm = create_algorithm(selected_algo)

            # Create progress display with context manager
            with WipeProgressDisplay() as progress_display:
                # Setup progress tracking
                progress_display.start_wipe_operation(
                    device_path=selected_device.path,
                    device_size=selected_device.capacity_bytes,
                    algorithm_name=algorithm.get_description(),
                    total_passes=algorithm.get_total_passes()
                )

                # Create progress callback
                def progress_callback(progress_info):
                    if progress_info.current_pass != progress_display.current_pass:
                        # New pass started
                        if progress_display.current_pass > 0:
                            progress_display.complete_pass()

                        current_pass = algorithm.get_passes()[progress_info.current_pass - 1]
                        progress_display.start_pass(
                            progress_info.current_pass,
                            current_pass.description
                        )

                    # Update progress based on bytes written
                    bytes_in_current_pass = int(progress_info.current_pass_progress * selected_device.capacity_bytes)
                    bytes_advance = bytes_in_current_pass - (progress_display.bytes_processed % selected_device.capacity_bytes)

                    if bytes_advance > 0:
                        progress_display.update_pass_progress(bytes_advance)

                # Create engine with progress callback
                engine_with_progress = WipeEngine(progress_callback=progress_callback)

                # Execute wipe with progress tracking
                result = engine_with_progress.wipe_device(
                    device_path=selected_device.path,
                    algorithm=algorithm,
                    verify=verify
                )

                # Complete the operation
                progress_display.complete_operation(success=result.success)

            if result.success:
                console.print("[green]✓ Wipe operation completed successfully![/green]")

                if generate_cert:
                    # Create proper WipeReport object
                    device_info = DeviceInfo(
                        path=selected_device.path,
                        model=selected_device.model,
                        serial=selected_device.serial,
                        capacity_bytes=selected_device.capacity_bytes,
                        capacity_human=selected_device.capacity_human,
                        device_type=str(selected_device.device_type),
                        interface=str(selected_device.interface),
                        vendor=selected_device.vendor,
                        firmware_version=selected_device.firmware_version,
                        wwn=selected_device.wwn
                    )

                    # Create pass result
                    pass_result = WipePassResult(
                        pass_number=1,
                        algorithm=result.algorithm_used,
                        pattern_description=algorithm.get_passes()[0].description,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        bytes_written=result.total_bytes_written,
                        success=result.success
                    )

                    # Create verification result if verification was performed
                    verification_result = None
                    if verify:
                        verification_result = VerificationResult(
                            verification_type="pattern_check",
                            passed=result.verification_passed
                        )

                    # Create complete report
                    wipe_report = WipeReport(
                        device_info=device_info,
                        algorithm_used=result.algorithm_used,
                        wipe_method="software",
                        start_time=result.start_time,
                        end_time=result.end_time,
                        total_passes=result.total_passes,
                        success=result.success,
                        pass_results=[pass_result],
                        verification_result=verification_result,
                        total_bytes_written=result.total_bytes_written,
                        average_speed_mbps=result.average_speed_mbps,
                        standards_compliance=["NIST SP 800-88"] if "nist" in selected_algo else []
                    )

                    cert_files = self.cert_generator.generate_certificate(wipe_report)
                    for format_type, file_path in cert_files.items():
                        console.print(f"[green]✓ Certificate generated ({format_type}): {file_path}[/green]")
            else:
                console.print(f"[red]✗ Wipe operation failed: {result.error_message}[/red]")

        except Exception as e:
            console.print(f"[red]Error during wipe operation: {e}[/red]")