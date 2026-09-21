"""Tests for Open Graph / Twitter Card meta tag detection."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import social_meta


def _run_with_html(html: str):
    resp = mock.MagicMock()
    resp.text = html
    with mock.patch("requests.get", return_value=resp):
        return social_meta.run("https://example.com")


def test_full_og_and_twitter_tags():
    html = """
    <meta property="og:title" content="My Page">
    <meta property="og:description" content="A description">
    <meta property="og:image" content="https://example.com/img.png">
    <meta name="twitter:card" content="summary_large_image">
    """
    result = _run_with_html(html)
    assert result["has_basic_og"] is True
    assert result["has_twitter_card"] is True
    assert result["og_tags_missing"] == ["og:url", "og:type"]


def test_no_social_tags_at_all():
    result = _run_with_html("<html><head><title>x</title></head></html>")
    assert result["has_basic_og"] is False
    assert result["has_twitter_card"] is False
    assert len(result["og_tags_missing"]) == len(social_meta.OG_TAGS)


def test_partial_og_tags_not_counted_as_basic():
    """og:title alone isn't enough — has_basic_og requires title+desc+image."""
    html = '<meta property="og:title" content="Only title">'
    result = _run_with_html(html)
    assert result["has_basic_og"] is False


def test_empty_content_treated_as_missing():
    html = '<meta property="og:title" content="">'
    result = _run_with_html(html)
    assert "og:title" in result["og_tags_missing"]


def test_request_failure_reported():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.Timeout("timed out")):
        result = social_meta.run("https://example.com")
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
