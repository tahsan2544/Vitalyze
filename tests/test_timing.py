"""Tests for phase-level HTTP timing (DNS/TCP/TLS breakdown).

Uses mocked sockets throughout — no real network calls, matching the fact
that this project's CI environment (and the sandbox it was built in) may
not have outbound network access.
"""

import sys
import os
from unittest import mock
import socket as socket_module

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import timing


def test_timed_http_connection_populates_timings():
    fake_sock = mock.MagicMock()
    with mock.patch("socket.getaddrinfo",
                     return_value=[(socket_module.AF_INET, socket_module.SOCK_STREAM, 6, "", ("1.2.3.4", 80))]), \
         mock.patch("socket.socket", return_value=fake_sock):
        conn = timing.TimedHTTPConnection("example.com", 80, timeout=5)
        conn.connect()

    assert conn.timings["dns_ms"] >= 0
    assert conn.timings["tcp_connect_ms"] >= 0
    assert conn.timings["tls_handshake_ms"] is None
    assert conn.sock is fake_sock


def test_timed_https_connection_includes_tls_phase():
    fake_raw_sock = mock.MagicMock()
    fake_tls_sock = mock.MagicMock()
    fake_ctx = mock.MagicMock()
    fake_ctx.wrap_socket.return_value = fake_tls_sock

    with mock.patch("socket.getaddrinfo",
                     return_value=[(socket_module.AF_INET, socket_module.SOCK_STREAM, 6, "", ("1.2.3.4", 443))]), \
         mock.patch("socket.socket", return_value=fake_raw_sock):
        conn = timing.TimedHTTPSConnection("example.com", 443, timeout=5)
        conn._context = fake_ctx  # HTTPSConnection.__init__ always sets a real context; override for the test
        conn.connect()

    assert conn.timings["tls_handshake_ms"] is not None
    assert conn.timings["tls_handshake_ms"] >= 0
    assert conn.sock is fake_tls_sock
    fake_ctx.wrap_socket.assert_called_once_with(fake_raw_sock, server_hostname="example.com")


def test_single_request_success_flow():
    fake_conn = mock.MagicMock()
    fake_conn.timings = {"dns_ms": 5.0, "tcp_connect_ms": 10.0, "tls_handshake_ms": 20.0}

    fake_resp = mock.MagicMock()
    fake_resp.status = 200
    fake_resp.reason = "OK"
    fake_resp.version = 11
    fake_resp.getheader.return_value = "gzip"
    fake_resp.getheaders.return_value = [("Content-Type", "text/html")]
    fake_resp.read.return_value = b"x" * 1000
    fake_conn.getresponse.return_value = fake_resp

    with mock.patch("vitalyze.timing.TimedHTTPSConnection", return_value=fake_conn):
        result = timing.single_request("https://example.com/path?q=1", timeout=10)

    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["content_length"] == 1000
    assert result["dns_ms"] == 5.0
    assert result["tcp_connect_ms"] == 10.0
    assert result["tls_handshake_ms"] == 20.0
    assert result["total_ms"] >= result["ttfb_ms"] >= 0
    fake_conn.putrequest.assert_called_once_with("GET", "/path?q=1", skip_accept_encoding=False)


def test_single_request_handles_connection_error():
    with mock.patch("vitalyze.timing.TimedHTTPSConnection",
                     side_effect=OSError("connection refused")):
        result = timing.single_request("https://example.com/")

    assert result["success"] is False
    assert "connection refused" in result["error"]


def test_single_request_rejects_unparseable_url():
    result = timing.single_request("not a url")
    assert result["success"] is False


# --- run_session: connection-reuse (keep-alive) timing ---

def _fake_session_response(status=200, connection_header=""):
    r = mock.MagicMock()
    r.status = status
    r.reason = "OK"
    r.version = 11
    r.read.return_value = b"x" * 500
    r.getheader.return_value = connection_header
    return r


def test_run_session_first_cold_rest_warm():
    fake_conn = mock.MagicMock()
    fake_conn.timings = {"dns_ms": 5.0, "tcp_connect_ms": 10.0, "tls_handshake_ms": 20.0}
    fake_conn.getresponse.side_effect = [
        _fake_session_response(), _fake_session_response(), _fake_session_response()
    ]

    with mock.patch("vitalyze.timing.TimedHTTPSConnection", return_value=fake_conn):
        results = timing.run_session("https://example.com/", runs=3)

    assert len(results) == 3
    assert results[0]["warm"] is False
    assert results[1]["warm"] is True
    assert results[2]["warm"] is True
    assert results[0]["dns_ms"] == 5.0
    assert results[1]["dns_ms"] is None
    assert results[2]["tcp_connect_ms"] is None
    assert fake_conn.putrequest.call_count == 3


def test_run_session_stops_when_server_sends_connection_close():
    fake_conn = mock.MagicMock()
    fake_conn.timings = {"dns_ms": 1.0, "tcp_connect_ms": 1.0, "tls_handshake_ms": 1.0}
    fake_conn.getresponse.side_effect = [
        _fake_session_response(), _fake_session_response(connection_header="close")
    ]

    with mock.patch("vitalyze.timing.TimedHTTPSConnection", return_value=fake_conn):
        results = timing.run_session("https://example.com/", runs=5)

    assert len(results) == 2, "should stop after the server announces it's closing"


def test_run_session_handles_broken_connection_mid_session():
    fake_conn = mock.MagicMock()
    fake_conn.timings = {"dns_ms": 1.0, "tcp_connect_ms": 1.0, "tls_handshake_ms": 1.0}
    fake_conn.getresponse.side_effect = [
        _fake_session_response(), _fake_session_response(), ConnectionResetError("reset")
    ]

    with mock.patch("vitalyze.timing.TimedHTTPSConnection", return_value=fake_conn):
        results = timing.run_session("https://example.com/", runs=5)

    assert len(results) == 3
    assert results[0]["success"] and results[1]["success"]
    assert results[2]["success"] is False
    assert results[2]["warm"] is True, "a failure after successful requests should still be marked warm"


def test_run_session_single_run_has_no_warm_entries():
    fake_conn = mock.MagicMock()
    fake_conn.timings = {"dns_ms": 1.0, "tcp_connect_ms": 1.0, "tls_handshake_ms": None}
    fake_conn.getresponse.side_effect = [_fake_session_response()]

    with mock.patch("vitalyze.timing.TimedHTTPConnection", return_value=fake_conn):
        results = timing.run_session("http://example.com/", runs=1)

    assert len(results) == 1
    assert results[0]["warm"] is False


def test_run_session_rejects_unparseable_url():
    results = timing.run_session("not a url")
    assert results[0]["success"] is False


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
