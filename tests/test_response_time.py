"""Tests for response_time.py's cold-connection phase measurement and the
connection-reuse ("warm") supplementary measurement."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import response_time


def _cold_result(**overrides):
    base = {
        "success": True, "status_code": 200, "reason": "OK", "http_version": "HTTP/1.1",
        "content_length": 1000, "content_encoding": None,
        "dns_ms": 5.0, "tcp_connect_ms": 10.0, "tls_handshake_ms": 20.0,
        "ttfb_ms": 100.0, "download_ms": 15.0, "total_ms": 150.0,
    }
    base.update(overrides)
    return base


def test_run_includes_warm_key_on_success():
    with mock.patch("vitalyze.timing.single_request", return_value=_cold_result()), \
         mock.patch("vitalyze.timing.run_session", return_value=[
             dict(_cold_result(warm=False)),
             dict(_cold_result(warm=True, total_ms=30.0), dns_ms=None, tcp_connect_ms=None, tls_handshake_ms=None),
         ]):
        result = response_time.run("https://example.com", runs=2)

    assert result["success"] is True
    assert "warm" in result
    assert result["warm"]["success"] is True
    assert result["warm"]["requests_reused"] == 1
    assert result["warm"]["first_request_total_ms"] == 150.0


def test_warm_stats_computed_correctly_across_multiple_reused_requests():
    session_results = [dict(_cold_result(warm=False))] + [
        dict(_cold_result(warm=True, total_ms=t), dns_ms=None, tcp_connect_ms=None, tls_handshake_ms=None)
        for t in (20.0, 22.0, 18.0)
    ]
    with mock.patch("vitalyze.timing.single_request", return_value=_cold_result()), \
         mock.patch("vitalyze.timing.run_session", return_value=session_results):
        result = response_time.run("https://example.com", runs=4)

    warm = result["warm"]
    assert warm["requests_reused"] == 3
    assert warm["warm_total_ms"]["avg"] == 20.0


def test_warm_measurement_failure_does_not_fail_overall_result():
    with mock.patch("vitalyze.timing.single_request", return_value=_cold_result()), \
         mock.patch("vitalyze.timing.run_session", return_value=[
             {"success": False, "error": "connection refused", "warm": False}
         ]):
        result = response_time.run("https://example.com", runs=1)

    assert result["success"] is True  # main measurement still succeeded
    assert result["warm"]["success"] is False
    assert "connection refused" in result["warm"]["note"]


def test_single_run_has_zero_reused_requests():
    with mock.patch("vitalyze.timing.single_request", return_value=_cold_result()), \
         mock.patch("vitalyze.timing.run_session", return_value=[dict(_cold_result(warm=False))]):
        result = response_time.run("https://example.com", runs=1)

    assert result["warm"]["success"] is True
    assert result["warm"]["requests_reused"] == 0
    assert result["warm"]["warm_total_ms"] is None


def test_all_cold_requests_failing_still_attempts_warm_measurement():
    with mock.patch("vitalyze.timing.single_request", return_value={"success": False, "error": "timeout"}), \
         mock.patch("vitalyze.timing.run_session", return_value=[dict(_cold_result(warm=False))]) as m_session:
        result = response_time.run("https://example.com", runs=3)

    assert result["success"] is False
    assert "warm" in result
    m_session.assert_called_once()


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
