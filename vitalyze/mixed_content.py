"""Detects mixed content: HTTP resources (images, scripts, stylesheets,
iframes, media) loaded on an HTTPS page — the exact thing browsers show a
warning or outright block for.

Only meaningful when the page itself is HTTPS; an HTTP page loading HTTP
resources isn't "mixed" content, it's just an HTTP page. Protocol-relative
URLs (//cdn.example.com/x.png) are correctly NOT flagged — they inherit the
page's own scheme per RFC 3986, which urljoin() already handles correctly.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests

from . import colors

# Tag -> attribute(s) that reference an external resource.
RESOURCE_ATTRS = {
    "img": ["src"],
    "script": ["src"],
    "iframe": ["src"],
    "audio": ["src"],
    "video": ["src", "poster"],
    "source": ["src"],
}


class _MixedContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.resource_urls = []  # list of (tag, url)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if "stylesheet" in rel and attrs_dict.get("href"):
                self.resource_urls.append((tag, attrs_dict["href"]))
            return

        if tag in RESOURCE_ATTRS:
            for attr in RESOURCE_ATTRS[tag]:
                value = attrs_dict.get(attr)
                if value:
                    self.resource_urls.append((tag, value))


def run(url: str, timeout: int = 15) -> dict:
    parsed_page = urlsplit(url)
    if parsed_page.scheme != "https":
        return {
            "success": True,
            "applicable": False,
            "note": "Page is not served over HTTPS — mixed content doesn't apply.",
            "mixed_resources": [],
            "mixed_count": 0,
        }

    result = {"success": False, "applicable": True, "error": None}
    try:
        resp = requests.get(url, timeout=timeout)
        parser = _MixedContentParser()
        parser.feed(resp.text)

        mixed = []
        for tag, raw_url in parser.resource_urls:
            absolute = urljoin(url, raw_url)
            if absolute.startswith("http://"):
                mixed.append({"tag": tag, "url": absolute})

        result.update({
            "success": True,
            "total_resources_scanned": len(parser.resource_urls),
            "mixed_resources": mixed,
            "mixed_count": len(mixed),
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Mixed content check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    if not result.get("applicable", True):
        print(f"    {colors.dim(result['note'])}")
        return

    if result["mixed_count"] == 0:
        print(f"    {colors.ok('No mixed content')} "
              f"({result['total_resources_scanned']} resources scanned)")
        return

    message = f"{result['mixed_count']} HTTP resource(s) loaded on this HTTPS page"
    print(f"    {colors.bad(message)}")
    for item in result["mixed_resources"][:10]:
        print(f"      - <{item['tag']}> {item['url']}")
    if result["mixed_count"] > 10:
        print(f"      ... and {result['mixed_count'] - 10} more")
