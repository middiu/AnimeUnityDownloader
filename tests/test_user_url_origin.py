"""Tests that derived request URLs follow the user-supplied page URL.

The download site has changed domains before. These tests lock the rule that
the page URL the user pastes is the only origin used for info and embed
requests, including a ``.co`` host and a host that is not ``.so``.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.crawler.crawler import Crawler
from src.crawler.crawler_utils import (
    build_embed_url,
    build_info_api_url,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CO_PAGE = "https://www.animeunity.co/anime/1517-yuru-yuri"
_OTHER_PAGE = "http://mirror.example:8080/anime/9-demo/"
_HARDCODED_HOSTS = ("animeunity.so", "animeunity.co")


class UserUrlOriginTests(unittest.TestCase):
    """Derived anime URLs must use the origin of the URL the user entered."""

    def test_co_host_info_api_and_embed_stay_on_that_host(self) -> None:
        """A .co page URL produces info and embed URLs on that same .co host."""
        self.assertEqual(
            build_info_api_url(_CO_PAGE),
            "https://www.animeunity.co/info_api/1517-yuru-yuri",
        )
        self.assertEqual(
            build_embed_url(_CO_PAGE, "42"),
            "https://www.animeunity.co/embed-url/42",
        )

    def test_crawler_methods_use_the_user_origin(self) -> None:
        """Crawler URL builders do not swap in a hardcoded host."""
        # The builders are exercised without constructing Crawler, which would
        # hit the network to count episodes.
        crawler = Crawler.__new__(Crawler)
        crawler.page_url = _CO_PAGE
        self.assertEqual(
            crawler._generate_api_url(_CO_PAGE),  # pylint: disable=protected-access
            "https://www.animeunity.co/info_api/1517-yuru-yuri",
        )
        self.assertEqual(
            crawler._generate_episode_embed_urls(["9", "10"]),  # pylint: disable=protected-access
            [
                "https://www.animeunity.co/embed-url/9",
                "https://www.animeunity.co/embed-url/10",
            ],
        )

    def test_other_host_and_scheme_are_preserved(self) -> None:
        """Any host and scheme the user pastes is the one used for requests."""
        info_url = build_info_api_url(_OTHER_PAGE)
        self.assertEqual(
            info_url,
            "http://mirror.example:8080/info_api/9-demo",
        )
        self.assertEqual(
            build_embed_url(_OTHER_PAGE, "7"),
            "http://mirror.example:8080/embed-url/7",
        )
        self.assertNotIn("animeunity.so", info_url)

    def test_supplied_so_host_is_honored_but_not_required(self) -> None:
        """A .so URL still works when the user pastes one; it is not assumed."""
        page = "https://www.animeunity.so/anime/1517-yuru-yuri"
        self.assertEqual(
            build_info_api_url(page),
            "https://www.animeunity.so/info_api/1517-yuru-yuri",
        )
        self.assertNotIn("animeunity.so", build_info_api_url(_CO_PAGE))

    def test_query_string_is_not_copied_into_the_api_path(self) -> None:
        """Query strings stay out of the derived info API path."""
        page = "https://www.animeunity.co/anime/1517-yuru-yuri?ref=1"
        self.assertEqual(
            build_info_api_url(page),
            "https://www.animeunity.co/info_api/1517-yuru-yuri",
        )

    def test_application_sources_do_not_hardcode_a_download_host(self) -> None:
        """Runtime code must not name the old .so host or the new .co host."""
        roots = (
            _REPO_ROOT / "src",
            _REPO_ROOT / "anime_downloader.py",
            _REPO_ROOT / "main.py",
            _REPO_ROOT / "gui.py",
        )
        offenders: list[str] = []
        for root in roots:
            paths = root.rglob("*.py") if root.is_dir() else (root,)
            for path in paths:
                text = path.read_text(encoding="utf-8")
                offenders.extend(
                    f"{path}: {needle}"
                    for needle in _HARDCODED_HOSTS
                    if needle in text
                )
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
