"""Follows a redirect chain one hop at a time (no auto-follow), timing each
hop individually and detecting redirect loops or HTTP->HTTPS enforcement."""

import time
from urllib.parse import urljoin

import requests

from . import colors

MAX_HOPS = 10


def run(url: str, timeout: int = 15) -> dict:
    hops = []
    current = url
    seen = set()
    total_start = time.perf_counter()

    for _ in range(MAX_HOPS):
        if current in seen:
            return {
                "success": False,
                "error": "Redirect loop detected",
                "hops": hops,
            }
        seen.add(current)

        try:
            start = time.perf_counter()
            resp = requests.get(current, timeout=timeout, allow_redirects=False)
            elapsed = (time.perf_counter() - start) * 1000
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e), "hops": hops}

        hops.append({
            "url": current,
            "status_code": resp.status_code,
            "time_ms": round(elapsed, 2),
        })

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                break
            current = urljoin(current, location)
        else:
            break

    total_time = (time.perf_counter() - total_start) * 1000
    hop_count = max(0, len(hops) - 1)

    return {
        "success": True,
        "final_url": current,
        "hop_count": hop_count,
        "hops": hops,
        "total_redirect_time_ms": round(total_time, 2),
        "http_upgraded_to_https": _upgrades_to_https(hops),
    }


def _upgrades_to_https(hops) -> bool:
    """True if the chain starts on http:// and ends on https://."""
    if len(hops) < 2:
        return False
    return hops[0]["url"].startswith("http://") and hops[-1]["url"].startswith("https://")


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Redirect check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    if result["hop_count"] == 0:
        print(f"    {colors.ok('No redirects')} — direct 2xx/4xx/5xx response.")
        return

    print(f"    Redirect hops:    {result['hop_count']}")
    print(f"    Total time:       {result['total_redirect_time_ms']} ms")
    upgrade_text = "yes" if result["http_upgraded_to_https"] else "no"
    upgrade_line = colors.ok(upgrade_text) if result["http_upgraded_to_https"] else upgrade_text
    print(f"    HTTP -> HTTPS:    {upgrade_line}")
    for i, hop in enumerate(result["hops"]):
        arrow = "  ->" if i > 0 else "    "
        print(f"    {arrow} [{hop['status_code']}] {hop['url']} ({hop['time_ms']} ms)")
    print(f"    Final URL:        {result['final_url']}")

    if result["hop_count"] >= 3:
        message = f"{result['hop_count']} redirects adds noticeable latency — consider flattening the chain"
        print(f"    {colors.warn(message)}")
