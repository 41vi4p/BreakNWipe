"""
Expert Mode for BreakNWipe CLI

Provides direct command-line access to wiping operations for advanced users.
"""

import sys
from pathlib import Path
from typing import Optional
from rich.console import Console

from ..device import DeviceDetector, DeviceHandler
from ..wipe_engine import WipeEngine, AlgorithmType, create_algorithm
from ..certificate import CertificateGenerator
from ..certificate.report import WipeReport, DeviceInfo, WipePassResult, VerificationResult
from .progress import WipeProgressDisplay

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
        except Exception as e:
            console.print(f"[red]Error accessing device {device}: {e}[/red]")
            return

        if not device_info:
            console.print(f"[red]Error:[/red] '{device}' is not a valid, accessible block device.")
            return

        console.print(f"Device: {device_info.model} ({device_info.capacity_human})")

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
            # Create algorithm instance from string
            algorithm_instance = create_algorithm(algorithm, passes=passes)

            if not dry_run:
                # Create progress display for actual wipe operations
                with WipeProgressDisplay() as progress_display:
                    # Setup progress tracking
                    progress_display.start_wipe_operation(
                        device_path=device,
                        device_size=device_info.capacity_bytes,
                        algorithm_name=algorithm_instance.get_description(),
                        total_passes=algorithm_instance.get_total_passes()
                    )

                    # Create progress callback
                    def progress_callback(progress_info):
                        if progress_info.current_pass != progress_display.current_pass:
                            # New pass started
                            if progress_display.current_pass > 0:
                                progress_display.complete_pass()

                            current_pass = algorithm_instance.get_passes()[progress_info.current_pass - 1]
                            progress_display.start_pass(
                                progress_info.current_pass,
                                current_pass.description
                            )

                        # Update progress based on bytes written
                        bytes_in_current_pass = int(progress_info.current_pass_progress * device_info.capacity_bytes)
                        bytes_advance = bytes_in_current_pass - (progress_display.bytes_processed % device_info.capacity_bytes)

                        if bytes_advance > 0:
                            progress_display.update_pass_progress(bytes_advance)

                    # Create engine with progress callback
                    engine_with_progress = WipeEngine(progress_callback=progress_callback)

                    # Execute wipe with progress tracking
                    result = engine_with_progress.wipe_device(
                        device_path=device,
                        algorithm=algorithm_instance,
                        verify=verify,
                        dry_run=dry_run
                    )

                    # Complete the operation
                    progress_display.complete_operation(success=result.success)
            else:
                # For dry run, use regular engine without progress display
                result = self.engine.wipe_device(
                    device_path=device,
                    algorithm=algorithm_instance,
                    verify=verify,
                    dry_run=dry_run
                )

            if result.success:
                console.print("[green]✓ Wipe operation completed successfully![/green]")

                if generate_certificate and not dry_run:
                    # Create proper WipeReport object
                    device_info_obj = DeviceInfo(
                        path=device_info.path,
                        model=device_info.model,
                        serial=device_info.serial,
                        capacity_bytes=device_info.capacity_bytes,
                        capacity_human=device_info.capacity_human,
                        device_type=str(device_info.device_type),
                        interface=str(device_info.interface),
                        vendor=device_info.vendor,
                        firmware_version=device_info.firmware_version,
                        wwn=device_info.wwn
                    )

                    # Create pass result
                    pass_result = WipePassResult(
                        pass_number=1,
                        algorithm=result.algorithm_used,
                        pattern_description=algorithm_instance.get_passes()[0].description,
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
                        device_info=device_info_obj,
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
                        standards_compliance=["NIST SP 800-88"] if "nist" in algorithm else []
                    )

                    # Set output directory if specified
                    if output_dir:
                        output_path = Path(output_dir)
                        output_path.mkdir(parents=True, exist_ok=True)
                        # Store original output directory and restore after
                        original_output_dir = self.cert_generator.output_directory
                        self.cert_generator.output_directory = output_path

                    cert_files = self.cert_generator.generate_certificate(wipe_report)

                    # Restore original output directory if changed
                    if output_dir:
                        self.cert_generator.output_directory = original_output_dir

                    for format_type, file_path in cert_files.items():
                        console.print(f"[green]✓ Certificate generated ({format_type}): {file_path}[/green]")
            else:
                console.print(f"[red]✗ Wipe operation failed: {result.error_message}[/red]")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Error during wipe operation: {e}[/red]")
            sys.exit(1)