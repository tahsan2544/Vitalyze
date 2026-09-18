"""Tests for security header presence scoring and cookie flag analysis."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import security_headers as sh


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


def test_all_headers_present_scores_100():
    headers = {h: "x" for h in sh.CHECKED_HEADERS}
    with mock.patch("requests.get", return_value=_resp(headers=headers)):
        result = sh.run("https://example.com")
    assert result["score"] == 100
    assert result["headers_missing"] == []


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


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
