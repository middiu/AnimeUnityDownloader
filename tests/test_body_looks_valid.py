"""Tests for embed-body validation used by fetch_with_retries."""

from __future__ import annotations

import unittest

from src.crawler.crawler_utils import _body_looks_valid


class BodyLooksValidTests(unittest.TestCase):
    """Accept bare player URLs; reject Cloudflare challenge HTML."""

    def test_bare_vixcloud_url(self) -> None:
        """Plain-text vixcloud embed URL is valid."""
        body = (
            "https://vixcloud.co/embed/310757"
            "?token=abc&expires=123&canPlayFHD=1"
        )
        self.assertTrue(_body_looks_valid(body))

    def test_bare_url_on_other_host(self) -> None:
        """A bare https URL on a non-vixcloud host is still a valid embed body."""
        self.assertTrue(
            _body_looks_valid("https://cdn.example/embed/99?token=x"),
        )

    def test_multiline_bare_url(self) -> None:
        """Duplicate URL lines (as returned by some mirrors) still count."""
        url = "https://vixcloud.co/embed/1?token=a&expires=1"
        self.assertTrue(_body_looks_valid(f"{url}\n\n{url}\n"))

    def test_challenge_html_rejected(self) -> None:
        """Cloudflare challenge markers make the body invalid."""
        body = (
            "<!doctype html><html><body>"
            "challenge-platform cf-chl-bypass"
            "</body></html>"
        )
        self.assertFalse(_body_looks_valid(body))

    def test_empty_rejected(self) -> None:
        """Empty bodies are invalid."""
        self.assertFalse(_body_looks_valid(""))

    def test_iframe_marker_accepted(self) -> None:
        """Legacy HTML embed with an iframe marker is valid."""
        self.assertTrue(
            _body_looks_valid('<html><iframe src="https://vixcloud.co/x"></iframe>'),
        )


if __name__ == "__main__":
    unittest.main()
