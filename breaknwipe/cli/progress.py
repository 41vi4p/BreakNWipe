"""
Progress Display for BreakNWipe CLI

Provides progress tracking and display functionality for wipe operations.
"""

from typing import Optional
from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()


class ProgressDisplay:
    """Progress display handler for wipe operations."""

    def __init__(self):
        """Initialize progress display."""
        self.progress = Progress()
        self.task_id: Optional[TaskID] = None

    def start_operation(self, description: str, total: Optional[int] = None):
        """Start a progress operation."""
        self.task_id = self.progress.add_task(description, total=total)

    def update_progress(self, advance: int = 1, description: Optional[str] = None):
        """Update progress."""
        if self.task_id is not None:
            self.progress.update(self.task_id, advance=advance)
            if description:
                self.progress.update(self.task_id, description=description)

    def complete_operation(self):
        """Mark operation as complete."""
        if self.task_id is not None:
            self.progress.update(self.task_id, completed=True)

    def __enter__(self):
        """Context manager entry."""
        self.progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.progress.stop()