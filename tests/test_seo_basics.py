"""Tests for SEO extraction via the real HTML parser.

Several of these are deliberately the exact cases a regex-based approach
gets wrong: attribute order, quote style, multi-line tags, and mixed case.
That's the point of this module — these should all still pass.
"""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import seo_basics


def _run_with_html(html: str, robots=True, sitemap=False) -> dict:
    resp = mock.MagicMock()
    resp.text = html
    with mock.patch("requests.get", return_value=resp), \
         mock.patch.object(seo_basics, "_check_url_exists", side_effect=[robots, sitemap]):
        return seo_basics.run("https://example.com")


def test_basic_extraction():
    html = """
    <html><head>
    <title>My Page</title>
    <meta name="description" content="A great page">
    <meta name="viewport" content="width=device-width">
    <link rel="canonical" href="https://example.com/">
    </head><body><h1>Hello</h1></body></html>
    """
    result = _run_with_html(html)
    assert result["title"] == "My Page"
    assert result["meta_description"] == "A great page"
    assert result["has_viewport_meta"] is True
    assert result["has_canonical"] is True
    assert result["h1_count"] == 1


def test_attribute_order_reversed():
    """content before name — a regex anchored on name-then-content order
    would miss this; attribute order in HTML is not meaningful."""
    html = '<meta content="Reversed order desc" name="description">'
    result = _run_with_html(html)
    assert result["meta_description"] == "Reversed order desc"


def test_single_quoted_attributes():
    html = "<meta name='description' content='Single quoted desc'>"
    result = _run_with_html(html)
    assert result["meta_description"] == "Single quoted desc"


def test_unquoted_attributes():
    html = "<meta name=description content=UnquotedDesc>"
    result = _run_with_html(html)
    assert result["meta_description"] == "UnquotedDesc"


def test_multiline_tag():
    """A tag whose attributes span multiple lines — common in
    hand-formatted or templated HTML."""
    html = """<meta
        name="description"
        content="Spans multiple lines">"""
    result = _run_with_html(html)
    assert result["meta_description"] == "Spans multiple lines"


def test_mixed_case_tags_and_attributes():
    html = '<TITLE>Mixed Case Title</TITLE><META NAME="Description" CONTENT="Mixed case desc">'
    result = _run_with_html(html)
    assert result["title"] == "Mixed Case Title"
    assert result["meta_description"] == "Mixed case desc"


def test_self_closing_meta_tag():
    html = '<meta name="viewport" content="width=device-width" />'
    result = _run_with_html(html)
    assert result["has_viewport_meta"] is True


def test_multiple_h1_tags_counted():
    html = "<h1>First</h1><p>text</p><h1>Second</h1>"
    result = _run_with_html(html)
    assert result["h1_count"] == 2


def test_missing_title_and_description():
    html = "<html><body><h1>Just a heading</h1></body></html>"
    result = _run_with_html(html)
    assert result["title"] is None
    assert result["title_length"] == 0
    assert result["meta_description"] is None
    assert result["meta_description_length"] == 0


def test_empty_title_tag_is_none_not_empty_string():
    html = "<title></title>"
    result = _run_with_html(html)
    assert result["title"] is None


def test_only_first_description_meta_used_if_duplicated():
    html = '<meta name="description" content="First"><meta name="description" content="Second">'
    result = _run_with_html(html)
    assert result["meta_description"] == "First"


def test_malformed_unclosed_tags_does_not_crash():
    """Real-world HTML is often not well-formed; the parser should degrade
    gracefully rather than raising."""
    html = '<html><head><title>Unclosed<meta name="viewport" content="x"><body><h1>Test'
    result = _run_with_html(html)
    assert result["success"] is True
    assert result["has_viewport_meta"] is True


def test_request_exception_reported():
    import requests as requests_module
    with mock.patch("requests.get", side_effect=requests_module.exceptions.Timeout("timed out")):
        result = seo_basics.run("https://example.com")
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
