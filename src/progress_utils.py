"""Utility functions for tracking download progress using the Rich library.

This module includes features for creating a progress bar and a formatted progress table
specifically designed for monitoring the download status of current taks. It also
provides CallbackProgress, a terminal-free reporter used by the graphical interface.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# Pattern matching rich markup tags (e.g. "[cyan]") embedded in task descriptions
_RICH_MARKUP_PATTERN = re.compile(r"\[[^\]]*\]")


def create_progress_bar() -> Progress:
    """Create a progress bar for tracking download progress."""
    return Progress(
        "{task.description}",
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        "•",
        TimeRemainingColumn(),
    )


def create_progress_table(title: str, job_progress: Progress) -> Table:
    """Create a progress table for tracking the download status of the current task."""
    progress_table = Table.grid()
    progress_table.add_row(
        Panel.fit(
            job_progress,
            title=f"[b]{title}",
            border_style="red",
            padding=(1, 1)),
    )
    return progress_table


class CallbackProgress:
    """Progress reporter that forwards rich-style events to a callback.

    Duck-types the subset of the rich Progress interface used by the download
    pipeline (``add_task``, ``update``, ``advance``) so that progress can be
    consumed by non-terminal clients such as the graphical interface. The
    ``add_task`` method must be called from a single thread (as run_in_parallel
    does); ``update`` and ``advance`` may be called from worker threads.
    """

    def __init__(self, callback: Callable[[dict], None]) -> None:
        """Store the callback that receives one event dictionary per update."""
        self._callback = callback
        self._next_task_id = 0

    def add_task(
        self,
        description: str,
        total: float | None = None,
        visible: bool = True,
    ) -> int:
        """Register a new task, emit its metadata, and return the task id."""
        task_id = self._next_task_id
        self._next_task_id += 1
        self._callback({
            "event": "task",
            "id": task_id,
            "desc": _RICH_MARKUP_PATTERN.sub("", description),
            "total": total,
            "visible": visible,
        })
        return task_id

    def update(
        self,
        task_id: int,
        completed: float | None = None,
        visible: bool | None = None,
    ) -> None:
        """Emit a progress update, including only the fields that are set."""
        event: dict = {"event": "update", "id": task_id}
        if completed is not None:
            event["completed"] = completed
        if visible is not None:
            event["visible"] = visible
        self._callback(event)

    def advance(self, task_id: int) -> None:
        """Emit a one-step advance for the given task."""
        self._callback({"event": "advance", "id": task_id})
