"""Checks security-relevant HTTP response headers, cookie flags (Secure/
HttpOnly/SameSite), and response compression."""

import re

import requests

from . import colors

CHECKED_HEADERS = {
    "Strict-Transport-Security": "Forces HTTPS, prevents downgrade attacks",
    "Content-Security-Policy": "Mitigates XSS and data injection attacks",
    "X-Content-Type-Options": "Prevents MIME-sniffing",
    "X-Frame-Options": "Mitigates clickjacking",
    "Referrer-Policy": "Controls referrer information leakage",
    "Permissions-Policy": "Restricts access to browser features/APIs",
}

COOKIE_SECURE_PENALTY = 10   # per cookie missing Secure on an https page
COOKIE_HTTPONLY_PENALTY = 5  # per cookie missing HttpOnly
MAX_COOKIE_PENALTY = 30

# Below this, an HSTS max-age is short enough that a single missed renewal
# window leaves a real gap in HTTPS enforcement.
HSTS_MIN_EFFECTIVE_SECONDS = 300
# The commonly recommended floor for a "solid" HSTS policy (~180 days).
HSTS_RECOMMENDED_SECONDS = 15552000


def _assess_header_quality(header: str, value: str):
    """Scores how much a present header's *value* actually helps, not just
    whether it exists. Returns (quality, note): quality is 1.0 (solid),
    0.5 (present but weak), or 0.0 (present but configured so poorly it
    provides ~no real protection). note is None when quality is 1.0.

    This deliberately only flags clearly-bad, well-known patterns (wildcard
    CSP sources, unsafe-inline, a too-short HSTS max-age, wrong-value
    X-Content-Type-Options) rather than trying to fully lint every
    possible header value — false positives on unusual-but-fine
    configurations are worse than missing a subtler weakness.
    """
    v = value.strip()
    v_lower = v.lower()

    if header == "Content-Security-Policy":
        if "unsafe-inline" in v_lower or "unsafe-eval" in v_lower:
            return 0.5, "contains unsafe-inline/unsafe-eval — weakens XSS protection"
        if re.search(r"(default-src|script-src)\s+\*(\s|;|$)", v_lower):
            return 0.0, "wildcard default-src/script-src — provides little real protection"
        return 1.0, None

    if header == "Strict-Transport-Security":
        match = re.search(r"max-age=(\d+)", v_lower)
        max_age = int(match.group(1)) if match else 0
        if max_age < HSTS_MIN_EFFECTIVE_SECONDS:
            return 0.0, f"max-age={max_age}s is too short to meaningfully enforce HTTPS"
        if max_age < HSTS_RECOMMENDED_SECONDS:
            return 0.5, f"max-age={max_age}s is shorter than the commonly recommended 180+ days"
        return 1.0, None

    if header == "X-Content-Type-Options":
        if v_lower != "nosniff":
            return 0.0, "only 'nosniff' has any effect — this value does nothing"
        return 1.0, None

    if header == "X-Frame-Options":
        if v_lower not in ("deny", "sameorigin"):
            return 0.5, "value is deprecated or non-standard (expected DENY or SAMEORIGIN)"
        return 1.0, None

    if header == "Referrer-Policy":
        if v_lower == "unsafe-url":
            return 0.5, "'unsafe-url' leaks the full URL to every cross-origin request"
        return 1.0, None

    if header == "Permissions-Policy":
        if not v:
            return 0.0, "present but empty"
        return 1.0, None

    return 1.0, None


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "headers_present": {}, "headers_missing": [], "score": 0, "error": None}

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        headers = {k: v for k, v in resp.headers.items()}
        is_https = resp.url.startswith("https://")

        present = {}
        missing = []
        quality_notes = {}
        weighted_score = 0.0
        for header, purpose in CHECKED_HEADERS.items():
            if header in headers:
                present[header] = headers[header]
                quality, note = _assess_header_quality(header, headers[header])
                weighted_score += quality
                if note:
                    quality_notes[header] = note
            else:
                missing.append({"header": header, "purpose": purpose})

        cookies_info = _analyze_cookies(resp)
        cookie_penalty = 0
        for cookie in cookies_info:
            if is_https and not cookie["secure"]:
                cookie_penalty += COOKIE_SECURE_PENALTY
            if not cookie["httponly"]:
                cookie_penalty += COOKIE_HTTPONLY_PENALTY
        cookie_penalty = min(cookie_penalty, MAX_COOKIE_PENALTY)

        base_score = round(weighted_score / len(CHECKED_HEADERS) * 100)
        final_score = max(0, base_score - cookie_penalty)

        result.update({
            "success": True,
            "status_code": resp.status_code,
            "server": headers.get("Server", "not disclosed"),
            "headers_present": present,
            "headers_missing": missing,
            "quality_notes": quality_notes,
            "content_encoding": headers.get("Content-Encoding", "none"),
            "cookies": cookies_info,
            "cookie_penalty": cookie_penalty,
            "score": final_score,
        })
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def _analyze_cookies(resp) -> list:
    """Extract Set-Cookie headers and check Secure/HttpOnly/SameSite flags.

    Prefers the raw urllib3 header list (getlist) since multiple Set-Cookie
    headers can't be safely comma-joined (Expires values contain commas).
    Falls back to the merged requests.Response.headers value if raw access
    isn't available for some reason.
    """
    set_cookie_headers = []
    try:
        set_cookie_headers = resp.raw.headers.getlist("Set-Cookie")
    except Exception:
        raw = resp.headers.get("Set-Cookie")
        if raw:
            set_cookie_headers = [raw]

    cookies_info = []
    for header_value in set_cookie_headers:
        name = header_value.split("=")[0].strip()
        parts = [p.strip().lower() for p in header_value.split(";")]
        samesite_match = re.search(r"samesite=([^;]+)", header_value, re.IGNORECASE)
        cookies_info.append({
            "name": name,
            "secure": "secure" in parts,
            "httponly": "httponly" in parts,
            "samesite": samesite_match.group(1).strip() if samesite_match else None,
        })

    return cookies_info


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"Header check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return

    print(f"    Server header:  {result['server']}")
    print(f"    Compression:    {result['content_encoding']}")
    penalty_note = f"(headers + cookie hygiene, penalty: -{result['cookie_penalty']})"
    print(f"    Score:          {colors.score_color(result['score'])}/100 {penalty_note}")
    quality_notes = result.get("quality_notes", {})
    for header, value in result["headers_present"].items():
        shown = value if len(value) < 60 else value[:57] + "..."
        line = f"{header}: {shown}"
        if header in quality_notes:
            print(f"      {colors.warn(line)}")
            print(f"        -> {quality_notes[header]}")
        else:
            print(f"      {colors.ok(line)}")
    for item in result["headers_missing"]:
        line = f"{item['header']} missing ({item['purpose']})"
        print(f"      {colors.bad(line)}")

    if result["cookies"]:
        print("    Cookies:")
        for c in result["cookies"]:
            flags = []
            if not c["secure"]:
                flags.append("missing Secure")
            if not c["httponly"]:
                flags.append("missing HttpOnly")
            if not c["samesite"]:
                flags.append("missing SameSite")
            if flags:
                line = f"{c['name']} ({', '.join(flags)})"
                print(f"      {colors.warn(line)}")
            else:
                print(f"      {colors.ok(c['name'])}")
