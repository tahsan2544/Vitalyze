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


def run(url: str, timeout: int = 15) -> dict:
    result = {"success": False, "headers_present": {}, "headers_missing": [], "score": 0, "error": None}

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        headers = {k: v for k, v in resp.headers.items()}
        is_https = resp.url.startswith("https://")

        present = {}
        missing = []
        for header, purpose in CHECKED_HEADERS.items():
            if header in headers:
                present[header] = headers[header]
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

        base_score = round(len(present) / len(CHECKED_HEADERS) * 100)
        final_score = max(0, base_score - cookie_penalty)

        result.update({
            "success": True,
            "status_code": resp.status_code,
            "server": headers.get("Server", "not disclosed"),
            "headers_present": present,
            "headers_missing": missing,
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
    for header, value in result["headers_present"].items():
        shown = value if len(value) < 60 else value[:57] + "..."
        line = f"{header}: {shown}"
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
