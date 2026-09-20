"""Basic on-page SEO and crawlability checks.

Uses html.parser.HTMLParser (standard library) instead of regex for
extracting title/meta/canonical/H1 — a real (if lightweight) parser
handles attribute order, quote style, self-closing tags, and case
variations that a regex pattern will quietly get wrong on real-world,
slightly-imperfect HTML.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from . import colors


class _SEOHTMLParser(HTMLParser):
    """Extracts exactly the handful of tags SEO checks care about, tolerant
    of the malformed-but-common HTML real sites actually ship."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1_count = 0
        self.has_viewport_meta = False
        self.has_canonical = False
        self.meta_description = None
        self._in_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            if name == "description" and self.meta_description is None:
                self.meta_description = attrs_dict.get("content")
            elif name == "viewport":
                self.has_viewport_meta = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel == "canonical":
                self.has_canonical = True

    # handle_startendtag (e.g. <meta ... />) delegates to handle_starttag +
    # handle_endtag by default — no override needed for void/self-closed tags.

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)

    @property
    def title(self):
        joined = "".join(self._title_parts).strip()
        return joined or None


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "error": None}

    try:
        resp = requests.get(url, timeout=timeout)
        parser = _SEOHTMLParser()
        parser.feed(resp.text)

        title = parser.title
        description = parser.meta_description.strip() if parser.meta_description else None

        robots_url = urljoin(url, "/robots.txt")
        sitemap_url = urljoin(url, "/sitemap.xml")
        robots_ok = _check_url_exists(robots_url, timeout)
        sitemap_ok = _check_url_exists(sitemap_url, timeout)

        result.update({
            "success": True,
            "title": title,
            "title_length": len(title) if title else 0,
            "meta_description": description,
            "meta_description_length": len(description) if description else 0,
            "h1_count": parser.h1_count,
            "has_viewport_meta": parser.has_viewport_meta,
            "has_canonical": parser.has_canonical,
            "robots_txt_found": robots_ok,
            "sitemap_xml_found": sitemap_ok,
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def _check_url_exists(url: str, timeout: int) -> bool:
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 405:  # some servers reject HEAD
            resp = requests.get(url, timeout=timeout)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"SEO check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    def yn(flag, good_text="yes", bad_text="no"):
        return colors.ok(good_text) if flag else colors.warn(bad_text)

    print(f"    Title:            {result['title']!r} ({result['title_length']} chars)")
    desc_text = "present" if result["meta_description"] else "MISSING"
    desc_colored = colors.ok(desc_text) if result["meta_description"] else colors.bad(desc_text)
    print(f"    Meta description: {desc_colored} ({result['meta_description_length']} chars)")
    print(f"    H1 tags:          {result['h1_count']}")
    print(f"    Viewport meta:    {yn(result['has_viewport_meta'])}")
    print(f"    Canonical tag:    {yn(result['has_canonical'])}")
    print(f"    robots.txt:       {yn(result['robots_txt_found'], 'found', 'not found')}")
    print(f"    sitemap.xml:      {yn(result['sitemap_xml_found'], 'found', 'not found')}")
