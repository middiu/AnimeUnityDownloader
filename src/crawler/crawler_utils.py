"""Crawler module of the project.

Module that provides functions to retrieve, extract, and process anime episode video
URLs from a web page.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import sys
from asyncio import Semaphore
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import requests

from src.config import (
    BASE_HEADERS,
    DOWNLOAD_LINK_PATTERN,
    prepare_headers,
)
from src.general_utils import prepare_cloudscraper_session

if TYPE_CHECKING:
    from bs4 import Tag
    from requests import Response


class MockResponse:
    """Wrapper around a `requests.Response` object that mimics its interface."""

    def __init__(self, response: Response) -> None:
        """Initialize a MockResponse with the given `requests.Response` object."""
        self.status_code = response.status_code
        self.text = response.text
        self.content = response.content
        self.headers = response.headers
        self._response = response

    def json(self) -> dict:
        """Return the JSON-decoded content of the response."""
        return self._response.json()

    def raise_for_status(self) -> None:
        """Raise an HTTPError if the HTTP request returned an unsuccessful status."""
        self._response.raise_for_status()


def validate_url(url: str) -> str:
    """Validate a URL by ensuring it does not have a trailing slash."""
    if url.endswith("/"):
        return url.rstrip("/")
    return url


def extract_host_domain(url: str) -> str:
    """Extract the host/domain name from a given URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc


def extract_name_from_title_tag(title_tag: Tag) -> str:
    """Extract the anime name from the title tag."""
    title_text = title_tag.string

    # Extract anime name from AnimeUnity title format
    if "AnimeUnity ~" in title_text:
        return title_text.split("AnimeUnity ~")[1].split("Streaming")[0].strip()

    # Fallback: Just use the title with cleanup
    return title_text.replace("AnimeUnity", "").replace("~", "").strip()


def validate_episode_range(
    start_episode: int | None,
    end_episode: int | None,
    num_episodes: int,
) -> None:
    """Validate the episode range to ensure it is within acceptable bounds."""

    def log_and_exit(message: str) -> None:
        logging.error(message)
        sys.exit(1)

    if start_episode and (start_episode < 1 or start_episode > num_episodes):
        log_and_exit(f"Start episode must be between 1 and {num_episodes}.")

    if start_episode and end_episode:
        if start_episode > end_episode:
            log_and_exit("Start episode cannot be greater than end episode.")

        if end_episode > num_episodes:
            log_and_exit(f"End episode must be between 1 and {num_episodes}.")


def episode_in_range(num: str, start: int | None, end: int | None) -> bool:
    """Check if episode number is within the specified range.

    The range is intended to be inclusive. If the episode number cannot be compared as
    a float, it is included by default. This assumes that the range is primarily used to
    exclude episodes, so the fallback behavior is to include everything unless
    explicitly excluded.
    """
    try:
        n = float(num)

    except ValueError:
        return True

    return (n >= start if start is not None else True) and (
        n <= end if end is not None else True
    )


async def fetch_with_cloudscraper(
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 15,
) -> dict | None:
    """Fetch data using cloudscraper as a fallback for Cloudflare protection."""
    scraper = prepare_cloudscraper_session()

    # Use provided headers or get new ones
    if headers is None:
        headers = prepare_headers()
        headers.update(BASE_HEADERS)

    try:
        # Make the request (cloudscraper is synchronous, so we need to handle this)
        response = scraper.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()

    except requests.exceptions.RequestException as req_err:
        log_message = f"Cloudscraper request to {url} failed: {req_err}"
        logging.exception(log_message)
        return None

    # Return a mock response object similar to httpx response
    return MockResponse(response)


async def fetch_with_retries(
    url: str,
    semaphore: Semaphore,
    headers: dict | None = None,
    params: dict | None = None,
    httpx_retries: int = 3,
    cloudflare_retries: int = 2,
) -> dict | None:
    # The retry-state machine has more arguments and early returns than the
    # project default. The branches are independent and flattening them would
    # obscure the control flow more than the metrics flag suggests.
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-return-statements
    """Fetch a URL with httpx + cloudscraper fallback.

    - 5xx responses: exponential backoff with jitter, up to ``httpx_retries``
      attempts, then a cloudscraper fallback (in case the edge is throwing
      challenges while the origin is up).
    - 403 responses: jump straight to the cloudscraper fallback (which solves
      Cloudflare's JS challenge).
    - 4xx (other than 403): treated as a hard failure. The URL is wrong or the
      resource is gone — retrying only delays the inevitable.
    - 2xx responses: validated against ``_body_looks_valid`` so a Cloudflare
      challenge page (HTTP 200 + challenge HTML) is rejected as a transient
      failure and retried. On the last attempt, falls through to the
      cloudscraper path.

    Returns the response on success, ``None`` on permanent failure. Never
    raises — callers should treat ``None`` as "could not resolve" and surface
    it as a per-episode error.
    """
    # Use better headers if none provided
    if headers is None:
        headers = prepare_headers()
        headers.update(BASE_HEADERS)

    # First try with httpx
    async with semaphore, httpx.AsyncClient(
        headers=headers,
        timeout=15,
        follow_redirects=True,
        verify=False,  # noqa: S501
    ) as client:
        for attempt in range(httpx_retries):
            try:
                response = await client.get(url, params=params)

            except httpx.RequestError:
                # Connection error / DNS / timeout. Retry with backoff; the
                # last attempt falls through to the cloudscraper path below.
                if attempt < httpx_retries - 1:
                    delay = 2 ** attempt + random.uniform(0.5, 1.5)  # noqa: S311
                    await asyncio.sleep(delay)
                    continue
                break

            status = response.status_code

            if status == httpx.codes.FORBIDDEN:
                # 403 → cloudscraper fallback (handles Cloudflare JS challenge).
                return await _try_cloudscraper(
                    url, headers, params, cloudflare_retries,
                )

            if status >= 500:
                # 5xx → backoff and retry; on the last attempt, give
                # cloudscraper one shot in case the origin is up but the edge
                # is throwing challenges.
                if attempt < httpx_retries - 1:
                    delay = 2 ** attempt + random.uniform(1, 2)  # noqa: S311
                    await asyncio.sleep(delay)
                    continue
                return await _try_cloudscraper(
                    url, headers, params, cloudflare_retries,
                )

            # 2xx (or 4xx non-403) — validate status, then body.
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                # 4xx other than 403. Hard failure; the URL is wrong or the
                # resource is gone. Do not retry.
                return None

            if _body_looks_valid(response.text):
                return response

            # 2xx but body looks like a Cloudflare challenge page. Treat as
            # a transient failure and retry; on the last attempt, give
            # cloudscraper a chance.
            if attempt < httpx_retries - 1:
                delay = 2 ** attempt + random.uniform(1, 2)  # noqa: S311
                await asyncio.sleep(delay)
                continue
            return await _try_cloudscraper(
                url, headers, params, cloudflare_retries,
            )

        # Reached only when the httpx loop completed without a return — i.e.
        # all attempts failed with RequestError. Try cloudscraper once.
        return await _try_cloudscraper(
            url, headers, params, cloudflare_retries,
        )

    return None


async def _try_cloudscraper(
    url: str,
    headers: dict | None,
    params: dict | None,
    retries: int,
) -> dict | None:
    """Cloudscraper fallback with its own retry budget.

    Returns the first response whose body passes ``_body_looks_valid``,
    otherwise ``None``. Each attempt is followed by an exponential backoff
    with jitter (except after the final attempt).
    """
    for attempt in range(retries):
        result = await fetch_with_cloudscraper(url, headers, params)
        if result is not None and _body_looks_valid(result.text):
            return result
        if attempt < retries - 1:
            delay = 2 ** attempt + random.uniform(0.5, 1.5)  # noqa: S311
            await asyncio.sleep(delay)
    return None


# Positive markers that indicate a real embed/player page. If any of these
# show up in the body, it's likely a legitimate response.
_BODY_VALID_MARKERS = (
    "<iframe",
    'src="https://vixcloud.co/',
    "player",
)

# Negative markers that explicitly identify a Cloudflare challenge page. If
# any of these show up, the body is rejected regardless of positive markers.
_BODY_INVALID_MARKERS = (
    "cf-chl-bypass",
    "challenge-platform",
    "cf-mitigated",
)


def _body_looks_valid(body: str) -> bool:
    """Return True if the body looks like a real embed page, not a challenge.

    A response is invalid if it is empty or contains any of the explicit
    Cloudflare challenge markers. Otherwise it is valid if it contains at
    least one of the positive embed/player markers. The negative check is
    sharp on purpose so a future embed-page redesign that drops one of the
    positive markers does not silently accept a challenge page.
    """
    if not body:
        return False
    lowered = body.lower()
    if any(marker in lowered for marker in _BODY_INVALID_MARKERS):
        return False
    return any(marker in lowered for marker in _BODY_VALID_MARKERS)


def extract_download_link(script_items: list, video_url: str) -> str | None:
    """Extract the download URL from a list of script items."""
    for item in script_items:
        match = re.search(DOWNLOAD_LINK_PATTERN, item.text)
        if match:
            return match.group(1)

    # Return None if no download link is found
    message = f"Error extracting the download link for {video_url}"
    logging.error(message)
    return None
