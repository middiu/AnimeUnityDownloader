"""Utilities for fetching web pages, managing directories, and clearing the terminal.

This module includes functions to handle common tasks such as sending HTTP requests,
parsing HTML, creating download directories, and  clearing the terminal, making it
reusable across projects.
"""

from __future__ import annotations

import gzip
import logging
import os
import random
import ssl
import sys
import time

import brotli
import cloudscraper
import httpx
import requests
import urllib3
from brotli import error as BrotliError  # noqa: N812
from bs4 import BeautifulSoup
from cloudscraper import CloudScraper
from cloudscraper import CipherSuiteAdapter

from .config import (
    DEFAULT_HEADERS,
    ENCODING_HEADERS,
    HTTP_STATUS_FORBIDDEN,
    MIN_CONTENT_LENGTH,
    prepare_headers,
)

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Python 3.14 tightened ssl.SSLContext: the C-level guard now raises
# ``ValueError: Cannot set verify_mode to CERT_NONE when check_hostname is
# enabled`` (and the symmetric case) if the two settings are out of sync.
#
# Two layers need patching for cloudscraper on 3.14:
#
# 1. ``urllib3.connection._ssl_wrap_socket_and_match_hostname`` writes
#    ``context.verify_mode = resolve_cert_reqs(cert_reqs)`` on the *incoming*
#    context (line 937). When ``cert_reqs == CERT_NONE`` and the context
#    still has ``check_hostname = True`` (the default from
#    ``ssl.create_default_context``), the 3.14 C-level guard fires. Patch
#    the function so it flips ``check_hostname = False`` *before* the
#    ``verify_mode`` write when ``cert_reqs`` is not ``CERT_REQUIRED``.
#
# 2. ``cloudscraper.CipherSuiteAdapter.wrap_socket`` itself does
#    ``self.ssl_context.check_hostname = False`` without touching
#    ``verify_mode``. Same problem: leaves the context inconsistent for
#    the next caller. Patch it to also set ``verify_mode = CERT_NONE``
#    (or ``CERT_REQUIRED`` in the no-SNI branch) so the context is
#    consistent before the underlying ``orig_wrap_socket`` runs.
def _ssl_wrap_socket_and_match_hostname_consistent(**kwargs):  # noqa: ANN001
    ssl_context = kwargs.get("ssl_context")
    cert_reqs = kwargs.get("cert_reqs")
    if ssl_context is not None and cert_reqs != ssl.CERT_REQUIRED:
        # Setting verify_mode=CERT_NONE while check_hostname is still True
        # is the exact 3.14 failure mode. Flip check_hostname off first.
        ssl_context.check_hostname = False
    return _ORIG_SSL_WRAP_SOCKET_AND_MATCH_HOSTNAME(**kwargs)


# Accessing the leading-underscore function on urllib3.connection is the
# whole point of the patch: we are replacing it. The other 3.14-safer
# alternative is to fork urllib3.
# pylint: disable=protected-access
_ORIG_SSL_WRAP_SOCKET_AND_MATCH_HOSTNAME = (
    urllib3.connection._ssl_wrap_socket_and_match_hostname
)
urllib3.connection._ssl_wrap_socket_and_match_hostname = (
    _ssl_wrap_socket_and_match_hostname_consistent
)
# pylint: enable=protected-access


def _wrap_socket_consistent_verify_mode(self, *args, **kwargs):  # noqa: ANN001
    if hasattr(self.ssl_context, "server_hostname") and self.ssl_context.server_hostname:
        kwargs["server_hostname"] = self.ssl_context.server_hostname
        self.ssl_context.check_hostname = False
        # Must follow the check_hostname flip: setting verify_mode=CERT_NONE
        # while check_hostname is still True is the exact 3.14 failure mode.
        self.ssl_context.verify_mode = ssl.CERT_NONE
    else:
        self.ssl_context.check_hostname = True
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
    return self.ssl_context.orig_wrap_socket(*args, **kwargs)


CipherSuiteAdapter.wrap_socket = _wrap_socket_consistent_verify_mode


def add_random_delay(min_delay: float = 0.5, max_delay: float = 2.0) -> None:
    """Add a random delay to avoid being detected as a bot."""
    delay = random.uniform(min_delay, max_delay)  # noqa: S311
    time.sleep(delay)


def prepare_cloudscraper_session() -> CloudScraper:
    """Create a cloudscraper session to mimic a Firefox browser on macOS."""
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "firefox",
            "platform": "darwin",  # macOS
            "desktop": True,
        },
    )

    # Disable SSL verification
    scraper.verify = False
    return scraper


def fetch_page_cloudflare(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch HTML content from a Cloudflare-protected webpage using cloudscraper."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Create a cloudscraper session with SSL verification disabled
    scraper = prepare_cloudscraper_session()

    # Get headers and update them
    headers = prepare_headers()
    headers.update(ENCODING_HEADERS)

    try:
        # Make the request using cloudscraper
        response = scraper.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

    except requests.RequestException as req_err:
        if (
            hasattr(req_err, "response")
            and req_err.response is not None
            and req_err.response.status_code == HTTP_STATUS_FORBIDDEN
        ):
            logging.exception("Cloudflare protection still blocking access")

        else:
            log_message = f"Request failed: {req_err}"
            logging.exception(log_message)

        # Re-raise the exception so calling code can handle it
        raise

    # Parse and return the HTML
    return BeautifulSoup(response.text, "html.parser")


def decompress_response(response: requests.Response) -> str:
    """Decompress the content of an HTTP response.

    Fall back to response.text if decompression fails.
    """
    encoding = response.headers.get("content-encoding", "").lower()

    try:
        if "br" in encoding:
            return brotli.decompress(response.content).decode("utf-8")

        if "gzip" in encoding:
            return gzip.decompress(response.content).decode("utf-8")

    except (BrotliError, OSError, UnicodeDecodeError) as decompress_err:
        log_message = (
            f"Decompression failed: {decompress_err}... using original response text"
        )
        logging.exception(log_message)

    return response.text


def fetch_page(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content of a webpage with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Create a new session per worker
    session = requests.Session()
    session.verify = False

    # Add additional headers to look more like a real browser
    headers = prepare_headers()
    headers.update(DEFAULT_HEADERS)

    try:
        # First attempt: normal request
        response = session.get(url, headers=headers, timeout=timeout, stream=False)
        response.raise_for_status()

        # Handle text content
        text_content = response.text

        # If we get binary/compressed content that wasn't auto-decompressed, try manual
        # decompression
        if len(text_content) < MIN_CONTENT_LENGTH or not any(
            tag in text_content.lower() for tag in ["<html", "<head", "<title"]
        ):
            text_content = decompress_response(response)

        return BeautifulSoup(text_content, "html.parser")

    except requests.RequestException as req_err:
        if (
            hasattr(req_err, "response")
            and req_err.response is not None
            and req_err.response.status_code == HTTP_STATUS_FORBIDDEN
        ):
            # Fallback to cloudscraper for Cloudflare protection
            try:
                return fetch_page_cloudflare(url, timeout)

            except requests.exceptions.RequestException as cf_err:
                log_message = f"Cloudscraper fallback failed for {url}: {cf_err}"
                logging.exception(log_message)
                sys.exit(1)

        message = f"Error fetching page {url}: {req_err}"
        logging.warning(message)
        sys.exit(1)


def fetch_page_httpx(url: str, timeout: int = 10) -> BeautifulSoup:
    """Fetch the HTML content using HTTPX with better bot detection avoidance."""
    # Add random delay to avoid bot detection
    add_random_delay()

    # Add additional headers to look more like a real browser
    headers = prepare_headers()
    headers.update(ENCODING_HEADERS)

    try:
        # First try with regular httpx
        with httpx.Client(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            verify=False,  # noqa: S501
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            # Get the properly decoded text content
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Try different parsing
            if not soup.find("html") and not soup.find("head"):
                logging.warning("Response doesn't appear to be valid HTML")
                soup = BeautifulSoup(html_content, "lxml")

            return soup

    except httpx.HTTPStatusError as https_err:
        if https_err.response.status_code == HTTP_STATUS_FORBIDDEN:
            # Fallback to cloudscraper for Cloudflare protection
            return fetch_page_cloudflare(url, timeout)

        raise


def clear_terminal() -> None:
    """Clear the terminal screen based on the operating system."""
    commands = {
        "nt": "cls",       # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        os.system(command)  # noqa: S605
