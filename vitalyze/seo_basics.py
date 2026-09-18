"""Basic on-page SEO and crawlability checks."""

import re
from urllib.parse import urljoin

import requests


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "error": None}

    try:
        resp = requests.get(url, timeout=timeout)
        html = resp.text

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else None

        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            html, re.IGNORECASE
        )
        description = desc_match.group(1).strip() if desc_match else None

        h1_count = len(re.findall(r"<h1[\s>]", html, re.IGNORECASE))
        viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
        canonical = bool(re.search(r'<link[^>]+rel=["\']canonical["\']', html, re.IGNORECASE))

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
            "h1_count": h1_count,
            "has_viewport_meta": viewport,
            "has_canonical": canonical,
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
        print(f"    [x] SEO check failed: {result['error']}")
        return

    print(f"    Title:            {result['title']!r} ({result['title_length']} chars)")
    print(f"    Meta description: {'present' if result['meta_description'] else 'MISSING'} "
          f"({result['meta_description_length']} chars)")
    print(f"    H1 tags:          {result['h1_count']}")
    print(f"    Viewport meta:    {'yes' if result['has_viewport_meta'] else 'no'}")
    print(f"    Canonical tag:    {'yes' if result['has_canonical'] else 'no'}")
    print(f"    robots.txt:       {'found' if result['robots_txt_found'] else 'not found'}")
    print(f"    sitemap.xml:      {'found' if result['sitemap_xml_found'] else 'not found'}")
