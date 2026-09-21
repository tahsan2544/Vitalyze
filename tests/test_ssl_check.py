"""Tests for ssl_check.py — certificate parsing and HTTP/2 ALPN detection.

Uses mocked sockets/SSL context throughout, matching the approach in
test_timing.py — no real network needed, and this sandbox/CI may not have
outbound network access anyway.
"""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import ssl_check


def _fake_cert(days_from_now_expiry=200):
    import datetime
    not_after = (datetime.datetime.now(datetime.timezone.utc) +
                 datetime.timedelta(days=days_from_now_expiry))
    not_before = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    return {
        "notAfter": not_after.strftime("%b %d %H:%M:%S %Y GMT"),
        "notBefore": not_before.strftime("%b %d %H:%M:%S %Y GMT"),
        "issuer": ((("organizationName", "TestCA"),),),
        "subject": ((("commonName", "example.com"),),),
    }


def _run_with_mocked_tls(alpn_protocol, days_from_now_expiry=200):
    fake_sock = mock.MagicMock()
    fake_ssock = mock.MagicMock()
    fake_ssock.__enter__.return_value = fake_ssock
    fake_ssock.getpeercert.return_value = _fake_cert(days_from_now_expiry)
    fake_ssock.version.return_value = "TLSv1.3"
    fake_ssock.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)
    fake_ssock.selected_alpn_protocol.return_value = alpn_protocol

    fake_ctx = mock.MagicMock()
    fake_ctx.wrap_socket.return_value = fake_ssock

    fake_conn = mock.MagicMock()
    fake_conn.__enter__.return_value = fake_sock

    with mock.patch("ssl.create_default_context", return_value=fake_ctx), \
         mock.patch("socket.create_connection", return_value=fake_conn):
        result = ssl_check.run("example.com")
    return result, fake_ctx


def test_http2_detected_when_alpn_negotiates_h2():
    result, fake_ctx = _run_with_mocked_tls(alpn_protocol="h2")
    assert result["success"] is True
    assert result["alpn_protocol"] == "h2"
    assert result["http2_supported"] is True
    fake_ctx.set_alpn_protocols.assert_called_once_with(["h2", "http/1.1"])


def test_http2_not_supported_when_alpn_negotiates_http11():
    result, _ = _run_with_mocked_tls(alpn_protocol="http/1.1")
    assert result["alpn_protocol"] == "http/1.1"
    assert result["http2_supported"] is False


def test_http2_not_supported_when_server_ignores_alpn():
    """Some servers don't support ALPN negotiation at all -> None."""
    result, _ = _run_with_mocked_tls(alpn_protocol=None)
    assert result["alpn_protocol"] is None
    assert result["http2_supported"] is False


def test_certificate_expiry_fields_still_correct():
    result, _ = _run_with_mocked_tls(alpn_protocol="h2", days_from_now_expiry=200)
    assert result["days_remaining"] in (199, 200)  # allow for test execution time drift
    assert result["expiring_soon"] is False
    assert result["issued_to"] == "example.com"
    assert result["issued_by"] == "TestCA"


def test_expiring_soon_flag():
    result, _ = _run_with_mocked_tls(alpn_protocol="h2", days_from_now_expiry=10)
    assert result["expiring_soon"] is True


def test_connection_error_reported():
    with mock.patch("ssl.create_default_context", side_effect=OSError("connection refused")):
        result = ssl_check.run("example.com")
    assert result["success"] is False
    assert "connection refused" in result["error"]


def test_port_parsed_from_netloc():
    fake_sock = mock.MagicMock()
    fake_ssock = mock.MagicMock()
    fake_ssock.__enter__.return_value = fake_ssock
    fake_ssock.getpeercert.return_value = _fake_cert()
    fake_ssock.version.return_value = "TLSv1.3"
    fake_ssock.cipher.return_value = ("X", "TLSv1.3", 256)
    fake_ssock.selected_alpn_protocol.return_value = "h2"
    fake_ctx = mock.MagicMock()
    fake_ctx.wrap_socket.return_value = fake_ssock
    fake_conn = mock.MagicMock()
    fake_conn.__enter__.return_value = fake_sock

    with mock.patch("ssl.create_default_context", return_value=fake_ctx), \
         mock.patch("socket.create_connection", return_value=fake_conn) as m_connect:
        ssl_check.run("example.com:8443")

    m_connect.assert_called_once_with(("example.com", 8443), timeout=mock.ANY)


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
