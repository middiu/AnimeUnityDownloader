"""Regression tests for the referer required by VixCloud embed pages."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from anime_downloader import download_anime, process_video_url
from src.general_utils import fetch_page

_VIDEO_URL = "https://vixcloud.example/embed/1?token=secret"
_PAGE_URL = "https://source.example/anime/1-demo"


class EmbedRefererTests(unittest.TestCase):
    """The source anime page must reach both embed-fetch code paths."""

    @patch("src.general_utils.add_random_delay")
    @patch("src.general_utils.requests.Session")
    def test_fetch_page_sends_referer(
        self,
        session_class: MagicMock,
        _delay: MagicMock,
    ) -> None:
        response = MagicMock()
        response.text = "<html><head><title>Player</title></head></html>"
        session = session_class.return_value
        session.get.return_value = response

        fetch_page(_VIDEO_URL, referer=_PAGE_URL)

        headers = session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Referer"], _PAGE_URL)

    @patch("src.general_utils.add_random_delay")
    @patch("src.general_utils.requests.Session")
    def test_cloudscraper_fallback_receives_referer(
        self,
        session_class: MagicMock,
        _delay: MagicMock,
    ) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=403),
        )
        session_class.return_value.get.return_value = response

        with patch("src.general_utils.fetch_page_cloudflare") as fallback:
            result = fetch_page(_VIDEO_URL, referer=_PAGE_URL)

        fallback.assert_called_once_with(_VIDEO_URL, 10, referer=_PAGE_URL)
        self.assertIs(result, fallback.return_value)

    @patch("anime_downloader.download_episode")
    @patch("anime_downloader.extract_download_link", return_value=None)
    @patch("anime_downloader.fetch_page")
    def test_process_video_url_forwards_referer(
        self,
        fetch: MagicMock,
        _extract: MagicMock,
        _download: MagicMock,
    ) -> None:
        fetch.return_value.find_all.return_value = []
        task_info = (MagicMock(), MagicMock(), MagicMock())

        process_video_url(
            _VIDEO_URL,
            "Downloads",
            task_info,
            referer=_PAGE_URL,
        )

        fetch.assert_called_once_with(_VIDEO_URL, referer=_PAGE_URL)

    @patch("anime_downloader.process_video_url")
    @patch("anime_downloader.run_in_parallel")
    def test_download_anime_binds_referer_to_worker(
        self,
        run_parallel: MagicMock,
        process: MagicMock,
    ) -> None:
        download_anime(
            "Demo",
            [_VIDEO_URL],
            "Downloads",
            progress_callback=lambda _event: None,
            referer=_PAGE_URL,
        )

        worker = run_parallel.call_args.args[0]
        task_info = (MagicMock(), MagicMock(), MagicMock())
        worker(_VIDEO_URL, "Downloads", task_info)
        process.assert_called_once_with(
            _VIDEO_URL,
            "Downloads",
            task_info,
            referer=_PAGE_URL,
        )


if __name__ == "__main__":
    unittest.main()
