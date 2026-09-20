"""Tests for security header presence scoring, content-quality scoring, and
cookie flag analysis."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import security_headers as sh

# Realistic strong values — used where a test needs "present AND effective",
# since a placeholder like "x" is present but not necessarily high-quality
# under content-aware scoring (see test_quality_* below for that).
STRONG_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=()",
}


def _resp(url="https://example.com/", headers=None, set_cookie_headers=None):
    resp = mock.MagicMock()
    resp.url = url
    resp.status_code = 200
    resp.headers = headers or {}
    if set_cookie_headers:
        resp.raw.headers.getlist.return_value = set_cookie_headers
    else:
        resp.raw.headers.getlist.return_value = []
    return resp


def test_all_headers_present_and_strong_scores_100():
    with mock.patch("requests.get", return_value=_resp(headers=STRONG_HEADERS)):
        result = sh.run("https://example.com")
    assert result["score"] == 100
    assert result["headers_missing"] == []
    assert result["quality_notes"] == {}


def test_no_headers_present_scores_0():
    with mock.patch("requests.get", return_value=_resp(headers={})):
        result = sh.run("https://example.com")
    assert result["score"] == 0
    assert len(result["headers_missing"]) == len(sh.CHECKED_HEADERS)


def test_secure_httponly_samesite_cookie_no_penalty():
    cookies = ["session=abc; Path=/; Secure; HttpOnly; SameSite=Strict"]
    with mock.patch("requests.get", return_value=_resp(set_cookie_headers=cookies)):
        result = sh.run("https://example.com")
    assert result["cookie_penalty"] == 0
    assert result["cookies"][0]["secure"] is True
    assert result["cookies"][0]["httponly"] is True
    assert result["cookies"][0]["samesite"] == "Strict"


def test_insecure_cookie_on_https_page_penalized():
    cookies = ["tracker=xyz; Path=/"]  # no Secure, no HttpOnly
    with mock.patch("requests.get", return_value=_resp(url="https://example.com/", set_cookie_headers=cookies)):
        result = sh.run("https://example.com")
    assert result["cookie_penalty"] == 15  # 10 (secure) + 5 (httponly)


def test_cookie_penalty_capped():
    # Many bad cookies shouldn't push the penalty past MAX_COOKIE_PENALTY
    cookies = ["c{}=x; Path=/".format(i) for i in range(10)]
    with mock.patch("requests.get", return_value=_resp(set_cookie_headers=cookies)):
        result = sh.run("https://example.com")
    assert result["cookie_penalty"] == sh.MAX_COOKIE_PENALTY


def test_score_never_goes_negative():
    cookies = ["c{}=x; Path=/".format(i) for i in range(10)]
    with mock.patch("requests.get", return_value=_resp(headers={}, set_cookie_headers=cookies)):
        result = sh.run("https://example.com")
    assert result["score"] >= 0


def test_getlist_failure_falls_back_gracefully():
    resp = mock.MagicMock()
    resp.url = "https://example.com/"
    resp.status_code = 200
    resp.headers = {"Set-Cookie": "session=abc; Secure; HttpOnly"}
    resp.raw.headers.getlist.side_effect = AttributeError("no getlist")
    with mock.patch("requests.get", return_value=resp):
        result = sh.run("https://example.com")
    assert result["success"] is True
    assert len(result["cookies"]) == 1


# --- Content-quality scoring: presence alone is not enough ---

def test_quality_csp_wildcard_source_scores_zero():
    quality, note = sh._assess_header_quality("Content-Security-Policy", "default-src *")
    assert quality == 0.0
    assert note is not None


def test_quality_csp_unsafe_inline_scores_half():
    quality, note = sh._assess_header_quality("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")
    assert quality == 0.5


def test_quality_csp_strict_scores_full():
    quality, note = sh._assess_header_quality("Content-Security-Policy", "default-src 'self'")
    assert quality == 1.0
    assert note is None


def test_quality_hsts_short_max_age_scores_zero():
    quality, note = sh._assess_header_quality("Strict-Transport-Security", "max-age=60")
    assert quality == 0.0


def test_quality_hsts_moderate_max_age_scores_half():
    quality, note = sh._assess_header_quality("Strict-Transport-Security", "max-age=86400")  # 1 day
    assert quality == 0.5


def test_quality_hsts_long_max_age_scores_full():
    quality, note = sh._assess_header_quality("Strict-Transport-Security", "max-age=31536000")  # 1 year
    assert quality == 1.0


def test_quality_hsts_missing_max_age_scores_zero():
    quality, note = sh._assess_header_quality("Strict-Transport-Security", "includeSubDomains")
    assert quality == 0.0


def test_quality_x_content_type_options_wrong_value_scores_zero():
    quality, note = sh._assess_header_quality("X-Content-Type-Options", "sniff-away")
    assert quality == 0.0


def test_quality_x_content_type_options_correct_value_scores_full():
    quality, note = sh._assess_header_quality("X-Content-Type-Options", "nosniff")
    assert quality == 1.0


def test_quality_x_frame_options_deprecated_value_scores_half():
    quality, note = sh._assess_header_quality("X-Frame-Options", "ALLOW-FROM https://example.com")
    assert quality == 0.5


def test_quality_x_frame_options_deny_scores_full():
    quality, note = sh._assess_header_quality("X-Frame-Options", "DENY")
    assert quality == 1.0


def test_quality_referrer_policy_unsafe_url_scores_half():
    quality, note = sh._assess_header_quality("Referrer-Policy", "unsafe-url")
    assert quality == 0.5


def test_quality_referrer_policy_strict_scores_full():
    quality, note = sh._assess_header_quality("Referrer-Policy", "no-referrer")
    assert quality == 1.0


def test_quality_permissions_policy_empty_scores_zero():
    quality, note = sh._assess_header_quality("Permissions-Policy", "")
    assert quality == 0.0


def test_weak_csp_scores_lower_than_strong_csp_end_to_end():
    """The whole point of this fix: two responses with the SAME headers
    present should NOT score the same if one header's value is garbage."""
    strong = dict(STRONG_HEADERS)
    weak = dict(STRONG_HEADERS, **{"Content-Security-Policy": "default-src *"})

    with mock.patch("requests.get", return_value=_resp(headers=strong)):
        strong_result = sh.run("https://example.com")
    with mock.patch("requests.get", return_value=_resp(headers=weak)):
        weak_result = sh.run("https://example.com")

    assert strong_result["score"] > weak_result["score"]
    assert "Content-Security-Policy" in weak_result["quality_notes"]


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
