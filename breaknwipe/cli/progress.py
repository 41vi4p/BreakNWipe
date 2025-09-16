"""
Progress Display for BreakNWipe CLI

Provides enhanced progress tracking and display functionality for wipe operations
with animations, ETA calculation, and speed monitoring.
"""

import time
from typing import Optional, Callable
from datetime import datetime, timedelta
from rich.console import Console
from rich.progress import (
    Progress, TaskID, BarColumn, TextColumn, TimeElapsedColumn,
    TimeRemainingColumn, SpinnerColumn, MofNCompleteColumn,
    TransferSpeedColumn, FileSizeColumn
)
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()


class WipeProgressDisplay:
    """Enhanced progress display for wipe operations with animations and ETA."""

    def __init__(self):
        """Initialize enhanced progress display."""
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(
                bar_width=40,
                style="cyan",
                complete_style="green",
                finished_style="green"
            ),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TransferSpeedColumn(),
            console=console,
            expand=True
        )

        self.main_task_id: Optional[TaskID] = None
        self.pass_task_id: Optional[TaskID] = None
        self.start_time: Optional[float] = None
        self.device_info: Optional[dict] = None
        self.algorithm_info: Optional[dict] = None
        self.current_pass = 0
        self.total_passes = 0
        self.bytes_processed = 0
        self.device_size = 0

    def start_wipe_operation(self, device_path: str, device_size: int,
                           algorithm_name: str, total_passes: int):
        """Start a wipe operation with device and algorithm info."""
        self.start_time = time.time()
        self.device_size = device_size
        self.total_passes = total_passes
        self.bytes_processed = 0
        self.current_pass = 0

        # Store device and algorithm info
        self.device_info = {
            "path": device_path,
            "size": device_size,
            "size_human": self._format_bytes(device_size)
        }
        self.algorithm_info = {
            "name": algorithm_name,
            "total_passes": total_passes
        }

        # Create main task for overall progress
        self.main_task_id = self.progress.add_task(
            f"[bold green]Wiping {device_path}[/bold green]",
            total=device_size * total_passes
        )

    def start_pass(self, pass_number: int, pass_description: str):
        """Start a new wipe pass."""
        self.current_pass = pass_number

        # Update or create pass task
        if self.pass_task_id is not None:
            self.progress.remove_task(self.pass_task_id)

        self.pass_task_id = self.progress.add_task(
            f"[cyan]Pass {pass_number}/{self.total_passes}: {pass_description}[/cyan]",
            total=self.device_size
        )

    def update_pass_progress(self, bytes_written: int):
        """Update progress for current pass."""
        if self.pass_task_id is not None:
            self.progress.update(
                self.pass_task_id,
                advance=bytes_written
            )

        if self.main_task_id is not None:
            self.progress.update(
                self.main_task_id,
                advance=bytes_written
            )

        self.bytes_processed += bytes_written

    def complete_pass(self):
        """Mark current pass as complete."""
        if self.pass_task_id is not None:
            self.progress.update(self.pass_task_id, completed=True)

    def complete_operation(self, success: bool = True):
        """Mark entire operation as complete."""
        if self.main_task_id is not None:
            if success:
                self.progress.update(self.main_task_id, completed=True)
                self.progress.update(
                    self.main_task_id,
                    description="[bold green]✓ Wipe completed successfully![/bold green]"
                )
            else:
                self.progress.update(
                    self.main_task_id,
                    description="[bold red]✗ Wipe failed![/bold red]"
                )

    def get_operation_stats(self) -> dict:
        """Get current operation statistics."""
        if not self.start_time:
            return {}

        elapsed = time.time() - self.start_time
        total_bytes = self.device_size * self.total_passes

        if elapsed > 0 and self.bytes_processed > 0:
            speed = self.bytes_processed / elapsed
            eta = (total_bytes - self.bytes_processed) / speed if speed > 0 else 0
        else:
            speed = 0
            eta = 0

        return {
            "elapsed": elapsed,
            "speed": speed,
            "speed_human": self._format_bytes(speed) + "/s" if speed > 0 else "0 B/s",
            "eta": eta,
            "eta_human": str(timedelta(seconds=int(eta))) if eta > 0 else "Unknown",
            "progress_percent": (self.bytes_processed / total_bytes * 100) if total_bytes > 0 else 0,
            "bytes_processed": self.bytes_processed,
            "bytes_processed_human": self._format_bytes(self.bytes_processed),
            "total_bytes": total_bytes,
            "total_bytes_human": self._format_bytes(total_bytes)
        }

    def create_info_panel(self) -> Panel:
        """Create an information panel showing operation details."""
        if not self.device_info or not self.algorithm_info:
            return Panel("No operation in progress", style="dim")

        stats = self.get_operation_stats()

        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="white")

        table.add_row("Device:", self.device_info["path"])
        table.add_row("Size:", self.device_info["size_human"])
        table.add_row("Algorithm:", self.algorithm_info["name"])
        table.add_row("Total Passes:", str(self.algorithm_info["total_passes"]))
        table.add_row("Current Pass:", f"{self.current_pass}/{self.total_passes}")

        if stats:
            table.add_row("", "")  # Spacer
            table.add_row("Speed:", stats["speed_human"])
            table.add_row("ETA:", stats["eta_human"])
            table.add_row("Processed:", f"{stats['bytes_processed_human']} / {stats['total_bytes_human']}")

        return Panel(
            table,
            title="[bold blue]Wipe Operation Status[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )

    def _format_bytes(self, bytes_val: float) -> str:
        """Format bytes into human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"

    def __enter__(self):
        """Context manager entry."""
        self.progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.progress.stop()


class ProgressDisplay(WipeProgressDisplay):
    """Backward compatibility alias."""
    pass