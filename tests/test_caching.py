"""Tests for Cache-Control/ETag/Last-Modified analysis."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import caching


def test_cacheable_with_max_age():
    resp = mock.MagicMock()
    resp.headers = {"Cache-Control": "public, max-age=3600"}
    with mock.patch("requests.get", return_value=resp):
        result = caching.run("https://example.com")
    assert result["success"] is True
    assert result["is_cacheable"] is True
    assert result["max_age_seconds"] == 3600


def test_no_store_is_not_cacheable():
    resp = mock.MagicMock()
    resp.headers = {"Cache-Control": "no-store"}
    with mock.patch("requests.get", return_value=resp):
        result = caching.run("https://example.com")
    assert result["is_cacheable"] is False


def test_private_is_not_cacheable():
    resp = mock.MagicMock()
    resp.headers = {"Cache-Control": "private, max-age=0"}
    with mock.patch("requests.get", return_value=resp):
        result = caching.run("https://example.com")
    assert result["is_cacheable"] is False


def test_no_cache_control_header_at_all():
    resp = mock.MagicMock()
    resp.headers = {}
    with mock.patch("requests.get", return_value=resp):
        result = caching.run("https://example.com")
    assert result["cache_control_raw"] is None
    assert result["is_cacheable"] is False
    assert result["max_age_seconds"] is None


def test_malformed_max_age_does_not_crash():
    resp = mock.MagicMock()
    resp.headers = {"Cache-Control": "max-age=notanumber"}
    with mock.patch("requests.get", return_value=resp):
        result = caching.run("https://example.com")
    assert result["success"] is True
    assert result["max_age_seconds"] is None


def test_request_failure_reported():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.Timeout("timed out")):
        result = caching.run("https://example.com")
    assert result["success"] is False
    assert "timed out" in result["error"]


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
