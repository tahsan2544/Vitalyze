"""Checks for Open Graph and Twitter Card meta tags — what controls how a
page appears when shared on social media or in chat link previews.

Deliberately informational only, no score contribution: missing OG tags is
a marketing/presentation gap, not a site defect, and folding it into the
overall health score would dilute what that score actually means. See
caching.py for the same reasoning applied to Cache-Control.
"""

from html.parser import HTMLParser

import requests

from . import colors

OG_TAGS = ["og:title", "og:description", "og:image", "og:url", "og:type"]
TWITTER_TAGS = ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]
OG_ESSENTIAL = ["og:title", "og:description", "og:image"]


class _SocialMetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og_tags = {}
        self.twitter_tags = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        # Convention: Open Graph tags use `property=`, Twitter Card tags use `name=`.
        key = attrs_dict.get("property") or attrs_dict.get("name")
        if not key:
            return
        key_lower = key.lower()
        content = attrs_dict.get("content", "")
        if key_lower in OG_TAGS and key_lower not in self.og_tags:
            self.og_tags[key_lower] = content
        elif key_lower in TWITTER_TAGS and key_lower not in self.twitter_tags:
            self.twitter_tags[key_lower] = content


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "error": None}
    try:
        resp = requests.get(url, timeout=timeout)
        parser = _SocialMetaParser()
        parser.feed(resp.text)

        og_missing = [t for t in OG_TAGS if not parser.og_tags.get(t)]
        twitter_missing = [t for t in TWITTER_TAGS if not parser.twitter_tags.get(t)]
        has_basic_og = all(parser.og_tags.get(t) for t in OG_ESSENTIAL)

        result.update({
            "success": True,
            "og_tags_present": parser.og_tags,
            "og_tags_missing": og_missing,
            "twitter_tags_present": parser.twitter_tags,
            "twitter_tags_missing": twitter_missing,
            "has_basic_og": has_basic_og,
            "has_twitter_card": bool(parser.twitter_tags.get("twitter:card")),
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
    return result


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Social meta check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    og_text = colors.ok("present") if result["has_basic_og"] else colors.warn("incomplete or missing")
    print(f"    Open Graph (title/desc/image): {og_text}")
    if result["og_tags_missing"]:
        print(f"      missing: {', '.join(result['og_tags_missing'])}")

    tw_text = colors.ok("present") if result["has_twitter_card"] else colors.warn("missing")
    print(f"    Twitter Card:                  {tw_text}")
