"""Tests for cloudscraper SSL verify=False behavior.

The Python 3.14 SSL patches must keep check_hostname in sync with verify_mode
without undoing ``scraper.verify = False``. Forcing CERT_REQUIRED in the
no-SNI wrap_socket branch caused SSLCertVerificationError on machines with
incomplete CA stores.
"""

from __future__ import annotations

import ssl
import unittest
from unittest.mock import MagicMock

from src.general_utils import (
    _wrap_socket_consistent_verify_mode,
    prepare_cloudscraper_session,
)


class CloudscraperSslVerifyTests(unittest.TestCase):
    """verify=False must survive the CipherSuiteAdapter wrap_socket patch."""

    def test_prepare_session_disables_adapter_ssl_verify(self) -> None:
        """Session and https adapter context both have verification off."""
        scraper = prepare_cloudscraper_session()
        self.assertFalse(scraper.verify)
        adapter = scraper.adapters["https://"]
        self.assertFalse(adapter.ssl_context.check_hostname)
        self.assertEqual(adapter.ssl_context.verify_mode, ssl.CERT_NONE)

    def test_wrap_socket_preserves_cert_none(self) -> None:
        """No-SNI wrap_socket must not re-enable CERT_REQUIRED after verify=False."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.orig_wrap_socket = MagicMock(return_value="wrapped")

        adapter = MagicMock()
        adapter.ssl_context = ctx

        result = _wrap_socket_consistent_verify_mode(adapter, "sock")

        self.assertEqual(result, "wrapped")
        self.assertFalse(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
        ctx.orig_wrap_socket.assert_called_once_with("sock")

    def test_wrap_socket_keeps_cert_required_when_verifying(self) -> None:
        """When verification is on, check_hostname stays True."""
        ctx = ssl.create_default_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        ctx.orig_wrap_socket = MagicMock(return_value="wrapped")

        adapter = MagicMock()
        adapter.ssl_context = ctx

        _wrap_socket_consistent_verify_mode(adapter, "sock")

        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_wrap_socket_sni_override_disables_hostname_check_only(self) -> None:
        """SNI override flips check_hostname off without forcing CERT_NONE."""
        ctx = ssl.create_default_context()
        ctx.server_hostname = "cdn.example"
        ctx.orig_wrap_socket = MagicMock(return_value="wrapped")

        adapter = MagicMock()
        adapter.ssl_context = ctx

        _wrap_socket_consistent_verify_mode(adapter, "sock")

        self.assertFalse(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        ctx.orig_wrap_socket.assert_called_once()
        _, kwargs = ctx.orig_wrap_socket.call_args
        self.assertEqual(kwargs.get("server_hostname"), "cdn.example")


if __name__ == "__main__":
    unittest.main()
