"""Tests for redirect chain following, loop detection, and HTTPS upgrade detection."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import redirects


def _resp(status, location=None):
    r = mock.MagicMock()
    r.status_code = status
    r.headers = {"Location": location} if location else {}
    return r


def test_no_redirect_direct_200():
    with mock.patch("requests.get", return_value=_resp(200)):
        result = redirects.run("https://example.com/")
    assert result["success"] is True
    assert result["hop_count"] == 0


def test_single_hop_http_to_https():
    responses = [_resp(301, "https://example.com/"), _resp(200)]
    with mock.patch("requests.get", side_effect=responses):
        result = redirects.run("http://example.com/")
    assert result["success"] is True
    assert result["hop_count"] == 1
    assert result["http_upgraded_to_https"] is True
    assert result["final_url"] == "https://example.com/"


def test_relative_location_resolved_against_current_url():
    responses = [_resp(302, "/new-path"), _resp(200)]
    with mock.patch("requests.get", side_effect=responses):
        result = redirects.run("https://example.com/old-path")
    assert result["final_url"] == "https://example.com/new-path"


def test_redirect_loop_detected():
    responses = [
        _resp(302, "http://example.com/b"),
        _resp(302, "http://example.com/a"),
        _resp(302, "http://example.com/b"),
    ]
    with mock.patch("requests.get", side_effect=responses):
        result = redirects.run("http://example.com/a")
    assert result["success"] is False
    assert "loop" in result["error"].lower()


def test_missing_location_header_stops_chain():
    with mock.patch("requests.get", return_value=_resp(301, location=None)):
        result = redirects.run("https://example.com/")
    assert result["success"] is True
    assert result["hop_count"] == 0


def test_request_exception_returns_failure():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.ConnectionError("refused")):
        result = redirects.run("https://example.com/")
    assert result["success"] is False
    assert "refused" in result["error"]


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
