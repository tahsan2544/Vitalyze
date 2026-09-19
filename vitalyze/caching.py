"""Analyzes HTTP caching directives: Cache-Control, ETag, Last-Modified, Vary.

This is informational/advisory — there's no single "correct" caching policy
for every site, so this reports what's configured rather than penalizing
absence the way security_headers does for missing security headers.
"""

import requests

from . import colors


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "error": None}

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        headers = resp.headers

        cache_control = headers.get("Cache-Control")
        directives = {}
        if cache_control:
            for part in cache_control.split(","):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    directives[key.strip().lower()] = val.strip()
                elif part:
                    directives[part.lower()] = True

        max_age = directives.get("max-age")
        try:
            max_age_seconds = int(max_age) if max_age is not None else None
        except (TypeError, ValueError):
            max_age_seconds = None

        result.update({
            "success": True,
            "cache_control_raw": cache_control,
            "cache_control_directives": directives,
            "max_age_seconds": max_age_seconds,
            "is_cacheable": bool(cache_control) and not any(
                d in directives for d in ("no-store", "no-cache", "private")
            ),
            "etag": headers.get("ETag"),
            "last_modified": headers.get("Last-Modified"),
            "vary": headers.get("Vary"),
            "expires": headers.get("Expires"),
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Caching check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    print(f"    Cache-Control:    {result['cache_control_raw'] or 'not set'}")
    if result["max_age_seconds"] is not None:
        hrs = result["max_age_seconds"] / 3600
        print(f"    Max-age:          {result['max_age_seconds']}s (~{hrs:.1f}h)")
    print(f"    ETag:             {result['etag'] or 'not set'}")
    print(f"    Last-Modified:    {result['last_modified'] or 'not set'}")
    print(f"    Vary:             {result['vary'] or 'not set'}")
    cacheable_text = colors.ok("yes") if result["is_cacheable"] else "no"
    print(f"    Cacheable:        {cacheable_text}")
