"""Basic, objectively-checkable accessibility signals: whether the page
declares a language, and what fraction of images have alt text.

Not a full WCAG audit — deliberately limited to checks that are
unambiguous from raw HTML alone (no rendering, no color-contrast analysis,
no keyboard-navigation testing). Presence of a non-empty alt attribute is
binary; there's no heuristic guessing involved.
"""

from html.parser import HTMLParser

import requests

from . import colors


class _A11yParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.image_count = 0
        self.images_with_alt = 0
        self.images_missing_alt = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "html":
            lang = attrs_dict.get("lang")
            if lang:
                self.html_lang = lang
        elif tag == "img":
            self.image_count += 1
            alt = attrs_dict.get("alt")
            if alt is not None and alt.strip() != "":
                self.images_with_alt += 1
            else:
                self.images_missing_alt.append(attrs_dict.get("src", "(no src)"))


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "error": None}
    try:
        resp = requests.get(url, timeout=timeout)
        parser = _A11yParser()
        parser.feed(resp.text)

        alt_coverage = (
            round(parser.images_with_alt / parser.image_count * 100)
            if parser.image_count > 0 else 100  # no images at all = nothing to fail on
        )

        result.update({
            "success": True,
            "has_lang_attribute": parser.html_lang is not None,
            "lang_value": parser.html_lang,
            "image_count": parser.image_count,
            "images_with_alt": parser.images_with_alt,
            "alt_text_coverage_pct": alt_coverage,
            "images_missing_alt": parser.images_missing_alt[:10],  # cap console/report noise
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
    return result


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Accessibility check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    if result["has_lang_attribute"]:
        print(f"    <html lang> attribute:  {colors.ok(repr(result['lang_value']))}")
    else:
        print(f"    <html lang> attribute:  {colors.bad('missing')}")

    if result["image_count"] == 0:
        print("    Images:                 none on page")
    else:
        coverage = result["alt_text_coverage_pct"]
        print(f"    Alt text coverage:      {colors.score_color(coverage)}% "
              f"({result['images_with_alt']}/{result['image_count']} images)")
        if result["images_missing_alt"]:
            print("    Images missing alt text:")
            for src in result["images_missing_alt"]:
                print(f"      - {src}")
