"""Tests for mixed-content (HTTP resources on an HTTPS page) detection."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import mixed_content


def _run_with_html(html: str, page_url="https://example.com/"):
    resp = mock.MagicMock()
    resp.text = html
    with mock.patch("requests.get", return_value=resp):
        return mixed_content.run(page_url)


def test_not_applicable_on_http_page():
    result = mixed_content.run("http://example.com/")
    assert result["applicable"] is False
    assert result["mixed_count"] == 0


def test_clean_https_page_no_mixed_content():
    html = '<img src="https://example.com/img.png"><script src="https://cdn.example.com/a.js"></script>'
    result = _run_with_html(html)
    assert result["mixed_count"] == 0
    assert result["total_resources_scanned"] == 2


def test_http_image_on_https_page_flagged():
    html = '<img src="http://insecure.example.com/img.png">'
    result = _run_with_html(html)
    assert result["mixed_count"] == 1
    assert result["mixed_resources"][0]["tag"] == "img"


def test_http_script_and_stylesheet_flagged():
    html = (
        '<script src="http://cdn.example.com/a.js"></script>'
        '<link rel="stylesheet" href="http://cdn.example.com/a.css">'
    )
    result = _run_with_html(html)
    assert result["mixed_count"] == 2


def test_protocol_relative_url_not_flagged():
    """//cdn.example.com/x.png inherits the page's own scheme (RFC 3986) —
    on an HTTPS page this resolves to HTTPS and is NOT mixed content."""
    html = '<img src="//cdn.example.com/logo.png">'
    result = _run_with_html(html)
    assert result["mixed_count"] == 0


def test_relative_path_not_flagged():
    html = '<img src="/images/logo.png">'
    result = _run_with_html(html)
    assert result["mixed_count"] == 0


def test_non_stylesheet_link_ignored():
    """A <link rel="canonical"> pointing at an http:// URL isn't mixed
    content in the browser-warning sense — only stylesheets load as a
    subresource; other rels (canonical, alternate, icon-as-metadata) don't
    trigger the browser's mixed-content blocking."""
    html = '<link rel="canonical" href="http://example.com/">'
    result = _run_with_html(html)
    assert result["mixed_count"] == 0


def test_data_uri_not_flagged():
    html = '<img src="data:image/png;base64,iVBORw0KGgo=">'
    result = _run_with_html(html)
    assert result["mixed_count"] == 0


def test_iframe_and_video_poster_checked():
    html = (
        '<iframe src="http://ads.example.com/frame.html"></iframe>'
        '<video poster="http://example.com/poster.jpg"></video>'
    )
    result = _run_with_html(html)
    assert result["mixed_count"] == 2


def test_request_failure_reported():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.Timeout("timed out")):
        result = mixed_content.run("https://example.com")
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
