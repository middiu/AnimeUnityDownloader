# AnimeUnity Downloader

> A Python-based tool for downloading anime series from AnimeUnity, featuring progress tracking for each episode. It efficiently extracts video URLs and manages downloads.

![Demo](https://github.com/Lysagxra/AnimeUnityDownloader/blob/8e274bdfb71f8fc714fa02322ec2b3eda61cce53/assets/demo.png)

## About this fork

This repository is a fork of [Lysagxra/AnimeUnityDownloader](https://github.com/Lysagxra/AnimeUnityDownloader). The core downloader, the crawler, the retry logic, and the rich-terminal progress path are **the work of [Lysagxra](https://github.com/Lysagxra)** — all credit for those goes to the original author.

The changes in this fork focus on the **desktop GUI** (a PySide6 wrapper around the same `anime_downloader.py` subprocess) and on keeping the embed/Cloudflare pipeline working as AnimeUnity's site evolves. See [Fork changes](#fork-changes) for the full list.

If you only need the command-line tool, the upstream README at [Lysagxra/AnimeUnityDownloader](https://github.com/Lysagxra/AnimeUnityDownloader) is authoritative.

## Features

- Downloads multiple episodes concurrently.
- Supports [batch downloading](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#batch-download) via a list of URLs.
- Supports downloading a [specified range of episodes](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#single-anime-download).
- Supports [custom download location](https://github.com/Lysagxra/AnimeUnityDownloader/tree/main?tab=readme-ov-file#file-download-location).
- Tracks download progress with a progress bar.
- Automatically creates a directory structure for organized storage.

## Dependencies

- Python 3
- `requests` - for HTTP requests
- `BeautifulSoup` (bs4) - for HTML parsing
- `rich` - for progress display in terminal
- `fake_useragent` - for generating fake user agents for web scraping
- `httpx` - for making asynchronous HTTP requests

The desktop GUI additionally uses `PySide6` (Qt), which is optional and listed in `requirements-gui.txt`.

<details>

<summary>Show directory structure</summary>

```
project-root/
├── src/
│ ├── crawler/
│ │ ├── crawler.py        # Module for crawling tasks
│ │ └── crawler_utils.py  # Utilities for extracting media download links
│ ├── gui/
│ │ ├── app.py            # Main window of the desktop interface
│ │ ├── theme.py          # Color palette and Qt stylesheet
│ │ └── worker.py          # QProcess orchestration of the downloader
│ ├── config.py           # Manages constants and settings used across the project
│ ├── download_utils.py   # Utilities for managing the download process
│ ├── file_utils.py       # Utilities for managing file operations
│ ├── general_utils.py    # Miscellaneous utility functions
│ └── progress_utils.py   # Tools for progress tracking and reporting
├── anime_downloader.py   # Module for downloading anime episodes
├── gui.py                # Entry point of the desktop interface
├── main.py               # Main script to run the downloader
└── URLs.txt              # Text file containing anime URLs
```

</details>

## Installation

1. Clone this fork (or the upstream — the CLI works identically):

```bash
git clone https://github.com/middiu/AnimeUnityDownloader.git
# or:
# git clone https://github.com/Lysagxra/AnimeUnityDownloader.git
```

2. Navigate to the project directory:

```bash
cd AnimeUnityDownloader
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. (Optional) To use the graphical interface, also install the GUI dependencies:

```bash
pip install -r requirements-gui.txt
```

## Graphical Interface (Optional)

A desktop application is available on top of the command-line tool. It wraps
`anime_downloader.py` in a native window with a dark theme and runs it as a
subprocess, so the CLI stays the canonical interface.

### Usage

```bash
python3 gui.py
```

### Features

- Paste an anime URL and choose between **All episodes**, a **Range** (`--start`/`--end`), or a specific **Episodes** list (`--episodes 1,3,7`).
- Select the download folder with the native OS folder picker; the choice is remembered across sessions. Files are saved in `<selected folder>/Downloads/<anime name>`, mirroring the CLI's `--custom-path` behavior.
- Tune **Parallel downloads** (1–16, default 2) to control how many episodes download at once via `--workers`. The last value is remembered across sessions.
- Per-episode failures surface as a red bar on the affected row (so cancelled runs and downloader failures are no longer indistinguishable), and failed URLs get up to 3 automatic retry passes (4 total attempts) before being marked failed.
- Each row's label starts as `Episode N/M` and is updated to `Episode N/M · filename` once the download link has been resolved, so the file under download is identifiable at a glance.
- Episode rows are always displayed in episode order (smallest task id on top) even if the `task` events arrive out of order.
- A small **Clear** button in the log card header wipes the log pane and the per-episode progress list in one click. It is disabled while a download is running so in-flight progress cannot be wiped accidentally.
- Live per-episode and overall progress bars, fed by the downloader's machine-readable `--progress-json` event stream.
- A **Cancel** button stops the download at any time. Note that the episode currently being downloaded is written directly to its final name, so a partial file may remain after cancelling.
- Errors and the downloader's stderr output are shown in a log pane.

## Single Anime Download

To download a single anime, you can use the `anime_downloader.py` script.

### Usage

Run the script followed by the anime URL you want to download:

```bash
python3 anime_downloader.py <anime_url> [--start <start_episode>] [--end <end_episode>] [--episodes <episode_list>] [--workers <count>]
```

- `<anime_url>`: The URL of the anime series.
- `--start <start_episode>`: The starting episode number (optional).
- `--end <end_episode>`: The ending episode number (optional).
- `--episodes <episode_list>`: Comma or space separated list of specific episode numbers to download.
- `--workers <count>`: Maximum number of episodes downloaded in parallel (default: 2).

### Examples

To download all episodes:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri
```

To download a specific range of episodes (e.g., episodes 5 to 10):
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --start 5 --end 10
```

To download episodes starting from a specific episode:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --start 5
```
In this case, the script will download all episodes starting from the `--start` episode to the last episode.

To download episodes up to a certain episode:
```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --end 10
```
In this case, the script will download all episodes starting from the first episode to the `--end` episode.

To download only specific episodes (e.g., episodes 3, 7, 12, and 15) add the `--episodes` flag and the list of episodes separated by comma or space or both

```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --episodes 3,7,12,15
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --episodes 3 7 12 15
```

This is useful when you already have some episodes and only need to download the missing ones, avoiding re-downloading an entire range.

To cap the number of episodes downloaded at the same time (defaults to 2), pass `--workers`:

```bash
python3 anime_downloader.py https://www.animeunity.so/anime/1517-yuru-yuri --workers 4
```

### Retry Behaviour

The embed-page fetcher (`fetch_with_retries`) retries on transient errors automatically:

- **5xx** (Cloudflare origin protection, etc.): up to 3 httpx attempts with exponential backoff and jitter, then a `cloudscraper` fallback.
- **403**: jumps straight to the `cloudscraper` fallback (handles Cloudflare's JS challenge).
- **2xx with a Cloudflare challenge body**: rejected by the body validator and retried through the same path.
- **4xx (other than 403)**: hard failure — the URL is wrong or the resource is gone.

If a single episode fails end-to-end (URL resolution + download), `run_in_parallel` retries it up to **3 extra passes** (4 total attempts) before marking the row failed.

## Batch Download

### Usage

1. Create a `URLs.txt` file in the project root and list the anime URLs you want to download.

- Example of `URLs.txt`:

```
https://www.animeunity.so/anime/1517-yuru-yuri
https://www.animeunity.so/anime/3871-chainsaw-man
https://www.animeunity.so/anime/2598-made-in-abyss
```

- Ensure that each URL is on its own line without any extra spaces.
- You can add as many URLs as you need, following the same format.

2. Run the main script via the command line:

```bash
python3 main.py
```

## File Download Location

If the `--custom-path <custom_path>` argument is used, the downloaded files will be saved in `<custom_path>/Downloads`. Otherwise, the files will be saved in a `Downloads` folder created within the script's directory

### Usage

```bash
python3 main.py --custom-path <custom_path>
```

### Example

```bash
python3 main.py --custom-path /path/to/external/drive
```

## Fork changes

Everything below diverges from [Lysagxra/AnimeUnityDownloader](https://github.com/Lysagxra/AnimeUnityDownloader). The CLI behaviour, the embed-page extractor, the retry/backoff logic, the rich progress bar, the URL/episode parsing, and the directory layout are upstream work — they have been kept intact and any bug fixes there have been sent (or will be sent) back upstream where they fit. Items marked **GUI** are new in this fork and only affect the PySide6 desktop interface.

### GUI features added in this fork

- **Per-row filename suffix** (v1.6.0). Each row's label starts as `Episode N/M` and is updated to `Episode N/M · filename` once the download link has been resolved, so the file under download is identifiable at a glance.
- **Sort by episode index** (v1.6.2). The progress list is always displayed in episode order — smallest task id on top — even if the `task` events arrive out of order.
- **Clear button** (v1.6.2). A small **Clear** button in the log card header wipes the log pane and the per-episode progress list in one click. It is disabled while a download is running so in-flight progress cannot be wiped accidentally.

### Embed/Cloudflare pipeline fixes (apply to both CLI and GUI)

- **`fetch_with_retries` body validator** (v1.5.0). A `validate_body` parameter was added so the JSON `/info_api/{id}/0` calls are not rejected by the embed-body validator, and so Cloudflare challenge pages (HTTP 200 + challenge HTML) are retried instead of being treated as success.
- **Bare vixcloud URL in the embed response** (v1.6.1). AnimeUnity's `/embed-url/{id}` endpoint now returns just the `vixcloud.co/embed/...` URL as plain text rather than wrapping it in an iframe. The endpoint accepts the bare URL, and the validator's positive-marker list recognises it.
- **`collect_video_urls` filters `None` results up front** (v1.6.0). The downstream pipeline is driven by URL counts (episode N/M labels, progress totals), so dropping unresolved embeds at the producer side avoids `fetch_page(None)` / "No scheme supplied" log spam and makes the per-episode task ids line up with the visible rows.

### Fork-specific cleanup

- The new GUI's worker signals and theme QSS live under `src/gui/` alongside the existing modules; nothing in `src/crawler/`, `src/download_utils.py`, `anime_downloader.py`, or `main.py` is reshaped for the GUI. The CLI and the GUI are still the same downloader — only the surface changed.
- Diagnostic `logging.info` calls were added in the crawler and `process_anime_download` during the v1.5.0/v1.6.0 debugging. They are low-volume and stay at `INFO` level so a user can run with `python3 anime_downloader.py …` and see what each batch is doing. Suppress by removing the `logging.basicConfig(level=logging.INFO, …)` call in `anime_downloader.py`.

## Credits

- Upstream project: [Lysagxra/AnimeUnityDownloader](https://github.com/Lysagxra/AnimeUnityDownloader) by [Lysagxra](https://github.com/Lysagxra). All downloader logic, retry behaviour, embed-page parsing, the rich progress display, and the batch/CLI scripts come from there. If you use this fork, please star the original.
- Fork maintainer: [middiu](https://github.com/middiu). The GUI-only additions and the embed-pipeline compatibility fixes listed under [Fork changes](#fork-changes) above.
