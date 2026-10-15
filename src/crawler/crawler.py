"""Module for automating the process of scraping anime videos based on episode ranges.

Utilities functions to crawl anime websites, retrieve episode information, and collect
video URLs for each episode.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

import httpx

from src.config import (
    ANIME_NAME_PATTERN,
    BATCH_SIZE,
    CRAWLER_WORKERS,
    prepare_headers,
)

from .crawler_utils import (
    episode_in_range,
    extract_host_domain,
    extract_name_from_title_tag,
    fetch_with_retries,
    validate_episode_range,
    validate_url,
)

if TYPE_CHECKING:
    from requests import BeautifulSoup

HEADERS = prepare_headers()


def _safe_float(value: str) -> float | None:
    """Convert a string to float, returning None if conversion fails."""
    try:
        return float(value)

    except (ValueError, TypeError):
        return None


class Crawler:
    """class responsible for crawling an anime.

    Extract episode IDs, generate embed URLs, and retrieve video URLs for a specified
    range of episodes.
    """

    def __init__(
        self,
        url: str,
        start_episode: int | None,
        end_episode: int | None,
        episodes: list[int] | None = None,
    ) -> None:
        """Initialize the crawler."""
        self.host_domain = extract_host_domain(url)
        self.api_url = self._generate_api_url(url)
        self.num_episodes = self._get_num_episodes()
        self.start_episode = start_episode
        self.end_episode = end_episode
        self.episodes = episodes
        self.semaphore = asyncio.Semaphore(CRAWLER_WORKERS)

    async def collect_video_urls(self) -> list[str]:
        """Collect a list of video URLs by concurrently fetching each embed URL.

        Episodes whose embed body could not be resolved are silently dropped
        from the result. The downstream pipeline is driven by URL counts
        (episode N/M labels, progress totals), and a None in the list would
        surface later as ``fetch_page(None)`` and "No scheme supplied" log
        spam. Better to skip the bad row up front.
        """
        episode_ids = await self._collect_episode_ids()
        embed_urls = self._generate_episode_embed_urls(episode_ids)
        tasks = [self._get_video_url(embed_url) for embed_url in embed_urls]
        results = await asyncio.gather(*tasks)
        non_null = [url for url in results if url is not None]
        none_count = len(results) - len(non_null)
        logging.info(
            "collect_video_urls: %d embeds resolved, %d dropped (None), sample=%s",
            len(non_null), none_count, non_null[:3],
        )
        return non_null

    # Static methods
    @staticmethod
    def extract_anime_name(soup: BeautifulSoup, url: str | None = None) -> str | None:
        """Extract the anime name from the provided BeautifulSoup object."""
        try:
            # First try the original method
            title_container = soup.find("h1", {"class": "title"})
            if title_container is not None:
                return title_container.get_text().strip()

            # Fallback: Extract from HTML title tag
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return extract_name_from_title_tag(title_tag)

            # If all else fails, try meta og:title
            og_title = soup.find("meta", property="og:title")
            if og_title:
                return og_title.get("content", "")

            # Last resort: Extract from URL
            if url:
                # URL pattern: /anime/ID-anime-name
                match = re.search(ANIME_NAME_PATTERN, url)
                if match:
                    return match.group(1).replace("-", " ").title()

        except AttributeError as attr_err:
            message = f"Error extracting anime name: {attr_err}"
            logging.exception(message)
            return ""

        logging.error("Could not extract anime name from any source")
        return None

    # Private methods
    def _get_num_episodes(self, timeout: int = 10) -> int:
        """Retrieve total number of episodes for the selected media."""
        response = httpx.get(
            url=self.api_url,
            headers=HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        response_json = response.json()
        return response_json["episodes_count"]

    def _generate_api_url(self, url: str) -> str | None:
        """Generate the API URL based on the provided base URL."""
        validated_url = validate_url(url)
        escaped_host_domain = re.escape(self.host_domain)
        match = re.match(
            rf"https://{escaped_host_domain}/anime/(\d+-[^/]+)",
            validated_url,
        )

        if match:
            anime_id = match.group(1)
            return f"https://{self.host_domain}/info_api/{anime_id}"

        logging.error("URL format is incorrect.")
        return None

    async def _get_episode_ids(self) -> list[tuple[int, str]] | None:
        """Fetch the IDs of all the episodes from an API."""
        episode_api_url = f"{self.api_url}/0"
        all_episode_infos = []
        start_range = 0
        end_range = self.num_episodes + 1
        logging.info(
            "_get_episode_ids: episode_api_url=%s num_episodes=%s",
            episode_api_url, self.num_episodes,
        )

        # To avoid request failures with very long series, we split the requests into
        # batches of size <= BATCH_SIZE (120).
        for batch_start in range(start_range, end_range, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE - 1, end_range)
            params = {
                "start_range": batch_start,
                "end_range": batch_end,
            }
            logging.info(
                "_get_episode_ids: batch params=%s", params,
            )

            # Perform the API request with retries and concurrency control.
            # The /info_api/{id}/0 endpoint returns JSON episode lists, not
            # the embed page body the validator expects, so opt out of body
            # validation for this call.
            response = await fetch_with_retries(
                episode_api_url,
                self.semaphore,
                headers=HEADERS,
                params=params,
                validate_body=False,
            )

            # Extract the list of episodes from the API response
            if response:
                response_json = response.json()
                logging.info(
                    "_get_episode_ids: batch response keys=%s episodes_count=%s episodes_len=%d",
                    list(response_json.keys()),
                    response_json.get("episodes_count"),
                    len(response_json.get("episodes", [])),
                )
                episode_infos = response_json.get("episodes", [])
                all_episode_infos.extend(episode_infos)
            else:
                logging.warning(
                    "_get_episode_ids: batch returned no response (all retries exhausted)",
                )

        logging.info(
            "_get_episode_ids: total collected=%d", len(all_episode_infos),
        )
        return [(info["id"], info["number"]) for info in all_episode_infos]

    async def _collect_episode_ids(self) -> list[str]:
        """Retrieve a list of episode IDs from a given URL."""
        logging.info(
            "_collect_episode_ids: start=%s end=%s episodes=%s",
            self.start_episode, self.end_episode, self.episodes,
        )
        episodes = await self._get_episode_ids()
        logging.info(
            "_collect_episode_ids: _get_episode_ids returned %d entries", len(episodes),
        )
        if self.episodes:
            episodes_set = {float(episode) for episode in self.episodes}
            logging.info(
                "_collect_episode_ids: filtering by explicit episodes=%s (as floats=%s)",
                self.episodes, episodes_set,
            )
            matched = [
                episode[0]
                for episode in episodes
                if _safe_float(episode[1]) in episodes_set
            ]
            logging.info(
                "_collect_episode_ids: explicit-episode match count=%d", len(matched),
            )
            return matched

        validate_episode_range(self.start_episode, self.end_episode, self.num_episodes)
        episodes = await self._get_episode_ids()
        logging.info(
            "_collect_episode_ids: re-fetched after validate_episode_range, %d entries",
            len(episodes),
        )

        return [
            episode[0]
            for episode in episodes
            if episode_in_range(episode[1], self.start_episode, self.end_episode)
        ]

    def _generate_episode_embed_urls(self, episode_ids: str) -> list[str]:
        """Generate a list of embed URLs for a series of episodes."""
        return [
            f"https://{self.host_domain}/embed-url/{episode_id}"
            for episode_id in episode_ids
        ]

    async def _get_video_url(self, embed_url: str) -> str | None:
        """Resolve an embed URL to the page that hosts the download link.

        The embed page is itself the page that contains
        ``<script>window.downloadUrl = '...'</script>``; ``process_video_url``
        re-fetches that page and runs ``extract_download_link`` over its
        script tags. So this method just needs to confirm the embed fetch
        succeeded (no Cloudflare challenge, not a 5xx) and pass the same
        URL through — the body itself is never used as a URL.

        Returns the embed URL on success, ``None`` when the embed fetch
        failed all retries (caller drops the entry from the batch).
        """
        response = await fetch_with_retries(
            embed_url,
            self.semaphore,
            headers=HEADERS,
        )

        if response is None:
            return None

        # Sanity-check the body so a Cloudflare challenge page slipping
        # through the validator is rejected here instead of becoming a
        # per-episode failure later. The embed page's HTML is large enough
        # that any real response will easily exceed this size.
        if len(response.text) < 200:
            return None

        return embed_url
