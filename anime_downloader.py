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

from src.config import parse_arguments, prepare_headers
from src.crawler.crawler import Crawler
from src.crawler.crawler_utils import extract_download_link
from src.download_utils import (
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
    """Download an episode from the download link and provides progress updates."""
    for attempt in range(retries):
        try:
            headers = prepare_headers()
            response = requests.get(
                download_link,
                stream=True,
                headers=headers,
                timeout=10,
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
            break


def process_video_url(video_url: str, download_path: str, task_info: tuple) -> None:
    """Process an embed URL to extract episode download links."""
    soup = fetch_page(video_url)
    script_items = soup.find_all("script")
    download_link = extract_download_link(script_items, video_url)
    download_episode(download_link, download_path, task_info)


def download_anime(
    anime_name: str,
    video_urls: list[str],
    download_path: str,
    progress_callback: Callable[[dict], None] | None = None,
) -> None:
    """Download episodes of a specified anime from provided video URLs."""
    if progress_callback is not None:
        job_progress = CallbackProgress(progress_callback)
        run_in_parallel(process_video_url, video_urls, job_progress, download_path)
        return

    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    with Live(progress_table, refresh_per_second=10):
        run_in_parallel(process_video_url, video_urls, job_progress, download_path)


# The download request is naturally described by these six parameters;
# bundling them would only obscure the signature shared with main.py.
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def process_anime_download(
    url: str,
    start_episode: int | None = None,
    end_episode: int | None = None,
    episodes: list[int] | None = None,
    custom_path: str | None = None,
    progress_callback: Callable[[dict], None] | None = None,
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
    download_anime(anime_name, video_urls, download_path, progress_callback)


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

    if not use_json:
        clear_terminal()
        await process_anime_download(
            args.url,
            start_episode=args.start,
            end_episode=args.end,
            episodes=episodes,
            custom_path=args.custom_path,
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
