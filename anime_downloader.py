"""Module to download anime episodes from a given AnimeUnity URL.

It extracts the anime ID, formats the anime name, retrieves episode URLs, and
downloads episodes concurrently.

Usage:
    - Run the script with the URL of the anime page as a command-line argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the anime name where each episode will be downloaded.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import requests
from rich.live import Live

from src.config import DOWNLOAD_WORKERS, parse_arguments, prepare_headers
from src.crawler.crawler import Crawler
from src.crawler.crawler_utils import extract_download_link
from src.download_utils import (
    READ_TIMEOUT,
    DownloadFailed,
    get_episode_filename,
    run_in_parallel,
    save_file_with_progress,
)
from src.file_utils import create_download_directory
from src.general_utils import clear_terminal, fetch_page, fetch_page_httpx
from src.progress_utils import (
    CallbackProgress,
    create_progress_bar,
    create_progress_table,
)


def download_episode(
    download_link: str,
    download_path: str,
    task_info: tuple,
    retries: int = 4,
) -> None:
    """Download an episode from the download link and provides progress updates.

    Raises ``DownloadFailed`` if the link is unusable, all retry attempts are
    exhausted, or the streaming response itself raises (e.g. mid-body read
    timeout from ``save_file_with_progress``).
    """
    if not download_link:
        raise DownloadFailed(f"no download link extracted for {download_path}")

    success = False
    for attempt in range(retries):
        try:
            headers = prepare_headers()
            response = requests.get(
                download_link,
                stream=True,
                headers=headers,
                timeout=(10, READ_TIMEOUT),
            )
            response.raise_for_status()

        except requests.RequestException:
            if attempt < retries - 1:
                delay = 10 * (attempt + 1) + random.uniform(1, 2)  # noqa: S311
                time.sleep(delay)

        else:
            filename = get_episode_filename(download_link)
            final_path = Path(download_path) / filename
            save_file_with_progress(response, final_path, task_info)
            success = True
            break

    if not success:
        raise DownloadFailed(
            f"exhausted {retries} retries for {download_link}",
        )


def process_video_url(video_url: str, download_path: str, task_info: tuple) -> None:
    """Process an embed URL to extract episode download links."""
    job_progress, task, _overall_task = task_info
    try:
        soup = fetch_page(video_url)
    except SystemExit as exit_error:
        # ``fetch_page`` calls ``sys.exit(1)`` on 403 / unrecoverable network
        # errors. Surface those as a per-episode failure so one bad URL does
        # not abort the whole batch.
        raise DownloadFailed(
            f"page fetch aborted (exit {exit_error.code}) for {video_url}",
        ) from exit_error
    script_items = soup.find_all("script")
    download_link = extract_download_link(script_items, video_url)
    if download_link and hasattr(job_progress, "update_task_name"):
        # The GUI appends the resolved file name to the row's label. The
        # rich terminal progress path uses ``create_progress_bar`` which
        # does not implement ``update_task_name``; the hasattr guard keeps
        # the terminal pipeline working without change.
        filename = get_episode_filename(download_link)
        if filename:
            job_progress.update_task_name(task, filename)
    download_episode(download_link, download_path, task_info)


def download_anime(
    anime_name: str,
    video_urls: list[str],
    download_path: str,
    progress_callback: Callable[[dict], None] | None = None,
    max_workers: int | None = None,
) -> None:
    """Download episodes of a specified anime from provided video URLs."""
    if progress_callback is not None:
        job_progress = CallbackProgress(progress_callback)
        run_in_parallel(
            process_video_url,
            video_urls,
            job_progress,
            download_path,
            max_workers=max_workers if max_workers is not None else DOWNLOAD_WORKERS,
        )
        return

    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    with Live(progress_table, refresh_per_second=10):
        run_in_parallel(
            process_video_url,
            video_urls,
            job_progress,
            download_path,
            max_workers=max_workers,
        )


# The download request is naturally described by these parameters; bundling them
# would only obscure the signature shared with main.py.
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def process_anime_download(
    url: str,
    start_episode: int | None = None,
    end_episode: int | None = None,
    episodes: list[int] | None = None,
    custom_path: str | None = None,
    progress_callback: Callable[[dict], None] | None = None,
    max_workers: int | None = None,
) -> None:
    """Process the download of an anime from the specified URL."""
    soup = fetch_page_httpx(url)
    crawler = Crawler(
        url=url,
        start_episode=start_episode,
        end_episode=end_episode,
        episodes=episodes,
    )
    anime_name = crawler.extract_anime_name(soup, url)
    download_path = create_download_directory(anime_name, custom_path=custom_path)

    if progress_callback is not None and anime_name:
        progress_callback({
            "event": "anime",
            "name": anime_name,
            "path": str(download_path),
        })

    video_urls = await crawler.collect_video_urls()
    download_anime(
        anime_name,
        video_urls,
        download_path,
        progress_callback,
        max_workers=max_workers,
    )


def parse_episodes_list(episodes_raw: list[str] | None) -> list[int] | None:
    """Parse episode tokens into a sorted list of ints.

    Accepts tokens like ['1,3,7,12'] or ['1,', '3,', '7', '12'] or ['1', '3', '7'].
    """
    if episodes_raw is None:
        return None

    merged = ",".join(episodes_raw)
    return sorted(
        int(episode.strip()) for episode in merged.split(",") if episode.strip()
    )


def make_json_emitter() -> Callable[[dict], None]:
    """Create a thread-safe emitter printing each event as one JSON stdout line."""
    lock = threading.Lock()

    def emit(event: dict) -> None:
        """Serialize and print a single progress event."""
        with lock:
            print(json.dumps(event), flush=True)

    return emit


async def main() -> None:
    """Execute the script to download anime episodes from a given AnimeUnity URL."""
    args = parse_arguments()
    use_json = args.progress_json
    episodes = parse_episodes_list(args.episodes)
    workers = getattr(args, "workers", None) or DOWNLOAD_WORKERS

    if not use_json:
        clear_terminal()
        await process_anime_download(
            args.url,
            start_episode=args.start,
            end_episode=args.end,
            episodes=episodes,
            custom_path=args.custom_path,
            max_workers=workers,
        )
        return

    emit = make_json_emitter()
    try:
        await process_anime_download(
            args.url,
            start_episode=args.start,
            end_episode=args.end,
            episodes=episodes,
            custom_path=args.custom_path,
            progress_callback=emit,
            max_workers=workers,
        )

    except SystemExit as exit_error:
        emit({
            "event": "error",
            "message": f"Download failed with exit code {exit_error.code}",
        })
        sys.exit(1)

    except Exception as exc:  # pylint: disable=broad-except
        emit({"event": "error", "message": f"{type(exc).__name__}: {exc}"})
        sys.exit(1)

    else:
        emit({"event": "done"})


if __name__ == "__main__":
    asyncio.run(main())
