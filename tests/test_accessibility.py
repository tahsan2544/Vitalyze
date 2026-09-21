"""Tests for basic accessibility checks: lang attribute, alt-text coverage."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import accessibility


def _run_with_html(html: str):
    resp = mock.MagicMock()
    resp.text = html
    with mock.patch("requests.get", return_value=resp):
        return accessibility.run("https://example.com")


def test_lang_attribute_detected():
    result = _run_with_html('<html lang="en"><body></body></html>')
    assert result["has_lang_attribute"] is True
    assert result["lang_value"] == "en"


def test_missing_lang_attribute():
    result = _run_with_html("<html><body></body></html>")
    assert result["has_lang_attribute"] is False
    assert result["lang_value"] is None


def test_no_images_scores_full_coverage():
    result = _run_with_html("<html lang='en'><body><p>No images here</p></body></html>")
    assert result["image_count"] == 0
    assert result["alt_text_coverage_pct"] == 100


def test_all_images_have_alt():
    html = '<img src="a.png" alt="A"><img src="b.png" alt="B">'
    result = _run_with_html(html)
    assert result["image_count"] == 2
    assert result["images_with_alt"] == 2
    assert result["alt_text_coverage_pct"] == 100


def test_partial_alt_coverage_calculated_correctly():
    html = '<img src="a.png" alt="A"><img src="b.png"><img src="c.png" alt="C">'
    result = _run_with_html(html)
    assert result["image_count"] == 3
    assert result["images_with_alt"] == 2
    assert result["alt_text_coverage_pct"] == 67  # round(2/3*100)
    assert result["images_missing_alt"] == ["b.png"]


def test_empty_alt_string_counts_as_missing():
    """alt="" is technically valid for decorative images in HTML, but for
    this simple objective check, an empty string doesn't demonstrate
    intentional decorative marking vs. an omitted attribute — treated the
    same as missing, conservatively."""
    html = '<img src="a.png" alt="">'
    result = _run_with_html(html)
    assert result["images_with_alt"] == 0
    assert result["alt_text_coverage_pct"] == 0


def test_images_missing_alt_capped_at_ten():
    html = "".join(f'<img src="img{i}.png">' for i in range(15))
    result = _run_with_html(html)
    assert result["image_count"] == 15
    assert len(result["images_missing_alt"]) == 10


def test_request_failure_reported():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.Timeout("timed out")):
        result = accessibility.run("https://example.com")
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
