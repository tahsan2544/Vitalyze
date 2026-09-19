"""Tests for regression-triggered webhook/Slack notifications."""

import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import alerts


def test_should_alert_no_trend_is_false():
    assert alerts.should_alert(None, 10) is False
    assert alerts.should_alert({}, 10) is False


def test_should_alert_triggers_on_overall_drop_past_threshold():
    assert alerts.should_alert({"overall": -15}, 10) is True


def test_should_alert_does_not_trigger_below_threshold():
    assert alerts.should_alert({"overall": -5}, 10) is False


def test_should_alert_exact_threshold_triggers():
    assert alerts.should_alert({"overall": -10}, 10) is True


def test_should_alert_triggers_on_any_single_category_drop():
    assert alerts.should_alert({"overall": -2, "ssl": -20}, 10) is True


def test_should_alert_ignores_improvements():
    assert alerts.should_alert({"overall": 20, "seo": 15}, 10) is False


def test_format_slack_text_includes_target_and_overall():
    text = alerts.format_slack_text("https://example.com", {"overall": 70}, {"overall": -15})
    assert "https://example.com" in text
    assert "70/100" in text
    assert "-15" in text


def test_format_slack_text_lists_dropped_categories_sorted_worst_first():
    text = alerts.format_slack_text(
        "https://example.com",
        {"overall": 70, "ssl": 60, "seo": 90},
        {"overall": -10, "ssl": -30, "seo": -5},
    )
    ssl_pos = text.index("ssl")
    seo_pos = text.index("seo")
    assert ssl_pos < seo_pos, "worse drop (ssl: -30) should be listed before smaller drop (seo: -5)"


def test_format_slack_text_no_trend_still_works():
    text = alerts.format_slack_text("https://example.com", {"overall": 90}, None)
    assert "90/100" in text
    assert "vs last run" not in text


def test_send_webhook_slack_success():
    fake_resp = mock.MagicMock(status_code=200)
    with mock.patch("requests.post", return_value=fake_resp) as m_post:
        result = alerts.send_webhook("https://hooks.slack.com/x", "https://example.com",
                                      {"overall": 70}, {"overall": -15})
    assert result["success"] is True
    payload = m_post.call_args.kwargs["json"]
    assert "text" in payload
    assert "example.com" in payload["text"]


def test_send_webhook_generic_format():
    fake_resp = mock.MagicMock(status_code=200)
    with mock.patch("requests.post", return_value=fake_resp) as m_post:
        result = alerts.send_webhook("https://example.com/hook", "https://mysite.com",
                                      {"overall": 70}, {"overall": -15}, webhook_format="generic")
    assert result["success"] is True
    payload = m_post.call_args.kwargs["json"]
    assert payload == {"target": "https://mysite.com", "scores": {"overall": 70}, "trend": {"overall": -15}}


def test_send_webhook_http_error_reported():
    fake_resp = mock.MagicMock(status_code=404)
    with mock.patch("requests.post", return_value=fake_resp):
        result = alerts.send_webhook("https://example.com/hook", "https://mysite.com", {}, {})
    assert result["success"] is False
    assert "404" in result["error"]


def test_send_webhook_connection_error_reported():
    import requests as requests_module
    with mock.patch("requests.post", side_effect=requests_module.exceptions.ConnectionError("refused")):
        result = alerts.send_webhook("https://example.com/hook", "https://mysite.com", {}, {})
    assert result["success"] is False
    assert "refused" in result["error"]


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
