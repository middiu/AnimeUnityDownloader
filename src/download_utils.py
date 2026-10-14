"""Utilities for handling file downloads with progress tracking."""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from .config import (
    DOWNLOAD_WORKERS,
    LARGE_FILE_CHUNK_SIZE,
    TASK_COLOR,
    THRESHOLDS,
)

if TYPE_CHECKING:
    from requests import Response
    from rich.progress import Progress

# Per-socket read timeout in seconds. Applied to the streaming response after
# the connection is established. ``requests`` translates ``timeout=(connect,
# read)`` into a urllib3 ``Timeout(connect, read)`` pair, so the connect budget
# stays independent of the (much longer) read budget.
READ_TIMEOUT = 30

# If no bytes arrive on the response stream for this many wall-clock seconds,
# ``save_file_with_progress`` raises ``DownloadFailed`` rather than blocking
# the worker indefinitely on a stalled CDN connection.
CHUNK_STALL_SECONDS = 30

# How many extra passes ``run_in_parallel`` makes for URLs that raised on the
# first attempt. One retry pass is the default; raise the constant to retry
# more times, or pass ``max_retry_passes=0`` to disable retries.
MAX_RETRY_PASSES = 1


class DownloadFailed(Exception):
    """Raised when an episode download cannot complete after all retries."""


def remove_special_characters(input_string: str) -> str:
    """Remove special characters from the input string."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "", input_string)


def get_episode_filename(download_link: str) -> str | None:
    """Extract the file name from the provided episode download link."""
    if download_link:
        try:
            filename = unquote(download_link.split("=")[-1])  # Original name
            return remove_special_characters(filename)        # Cleaned name

        except IndexError as indx_err:
            message = f"Error while extracting the file name: {indx_err}"
            logging.exception(message)

    return None


def get_chunk_size(file_size: int) -> int:
    """Determine the optimal chunk size based on the file size."""
    for threshold, chunk_size in THRESHOLDS:
        if file_size < threshold:
            return chunk_size

    return LARGE_FILE_CHUNK_SIZE


def save_file_with_progress(
    response: Response,
    final_path: str,
    task_info: tuple,
) -> None:
    """Save a file to the specified path while tracking and updating progress.

    Raises ``DownloadFailed`` if the connection stalls (no bytes received for
    ``CHUNK_STALL_SECONDS``) or a file-system error occurs mid-write.
    """
    # pylint: disable=too-many-locals
    job_progress, task, overall_task = task_info
    file_size = int(response.headers.get("Content-Length", -1))
    chunk_size = get_chunk_size(file_size)
    total_downloaded = 0
    # Tracks the last wall-clock instant bytes were received. The HTTP socket
    # read timeout would catch a fully-idle connection, but a trickle of bytes
    # (e.g. 1 byte every 9s) keeps the socket alive forever — the wall clock
    # is the only signal that the CDN has actually stopped sending data.
    last_chunk_at = time.monotonic()
    # Content-Length may be missing for chunked transfer-encoding responses;
    # treat that as "unknown size" and skip percentage updates until the first
    # chunk has actually arrived. Negative or zero file_size would otherwise
    # produce a negative progress percentage in the GUI.
    have_size = file_size > 0

    try:
        with Path(final_path).open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                now = time.monotonic()
                if now - last_chunk_at > CHUNK_STALL_SECONDS:
                    raise DownloadFailed(
                        f"stream stalled: no data for "
                        f"{int(now - last_chunk_at)}s",
                    )
                if chunk:
                    file.write(chunk)
                    total_downloaded += len(chunk)
                    last_chunk_at = now
                    if have_size:
                        progress_percentage = (total_downloaded / file_size) * 100
                        job_progress.update(task, completed=progress_percentage)

    except OSError as os_err:
        raise DownloadFailed(f"file write failed: {os_err}") from os_err

    job_progress.update(task, completed=100, visible=False)
    job_progress.advance(overall_task)


def run_in_parallel(
    func: callable,
    items: list,
    job_progress: Progress,
    *args: tuple,
    max_workers: int = DOWNLOAD_WORKERS,
    max_retry_passes: int = MAX_RETRY_PASSES,
) -> None:
    """Execute a function in parallel for a list of items, updating progress.

    Worker exceptions are captured and reported via
    ``job_progress.report_failure(task_id, message)``. Items that fail are
    re-submitted up to ``max_retry_passes`` extra times before being reported
    as failed for good. Each retry pass resets the per-episode task's
    visibility so the GUI shows it downloading again.
    """
    # pylint: disable=too-many-locals
    num_items = len(items)
    overall_task = job_progress.add_task(
        f"[{TASK_COLOR}]Progress", total=num_items, visible=True,
    )

    # Per-item task ids and the executor futures that work on them. Kept as
    # parallel lists keyed by index so a failed future can be matched back to
    # its (item, task_id) pair for the retry submission.
    task_ids: list[int] = [
        job_progress.add_task(
            f"[{TASK_COLOR}]Episode {indx + 1}/{num_items}",
            total=100,
            visible=False,
        )
        for indx in range(num_items)
    ]
    pending: list[tuple[int, object]] = list(enumerate(items))
    retry_pass = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while pending:
            futures: dict[Future, tuple[int, int]] = {}
            for index, item in pending:
                task_id = task_ids[index]
                task_info = (job_progress, task_id, overall_task)
                futures[executor.submit(func, item, *args, task_info)] = (
                    index, task_id,
                )

            failed: list[tuple[int, int, BaseException]] = []
            for future in as_completed(futures):
                index, task_id = futures[future]
                exc = future.exception()
                if exc is not None:
                    failed.append((index, task_id, exc))

            if not failed or retry_pass >= max_retry_passes:
                for _index, task_id, exc in failed:
                    if hasattr(job_progress, "report_failure"):
                        job_progress.report_failure(task_id, str(exc))
                pending = []
                continue

            # Retry only the items that failed; keep their original task ids
            # so the GUI row stays mapped to the same episode.
            retry_pass += 1
            pending = [(index, items[index]) for index, _task_id, _exc in failed]
            for _index, task_id, _exc in failed:
                job_progress.update(task_id, visible=True)
