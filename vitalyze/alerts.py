"""Sends a webhook notification when a scan's score drops compared to the
previous run. Two payload formats:

- "slack" (default): {"text": "..."} — the shape Slack incoming webhooks
  expect, and one several other chat tools accept as-is.
- "generic": raw {"target", "scores", "trend"} JSON, for a custom
  integration to parse itself (Discord, a custom endpoint, etc. — each
  expects its own shape, so "generic" hands over the data undecorated
  rather than guessing a format that might not match).
"""

import requests


def should_alert(trend: dict, threshold: int) -> bool:
    """True if the overall score, or any single category, dropped by more
    than `threshold` points versus the previous run. No previous run (or no
    trend at all) means nothing to alert on."""
    if not trend:
        return False
    return any(delta <= -threshold for delta in trend.values())


def format_slack_text(target: str, current_scores: dict, trend: dict) -> str:
    overall = current_scores.get("overall")
    overall_delta = trend.get("overall") if trend else None

    lines = [f"*Vitalyze alert for {target}*"]
    if overall is not None:
        delta_note = f" ({overall_delta:+d} vs last run)" if overall_delta is not None else ""
        lines.append(f"Overall score: {overall}/100{delta_note}")

    if trend:
        drops = {k: v for k, v in trend.items() if v < 0 and k != "overall"}
        if drops:
            lines.append("Categories that dropped:")
            for category, delta in sorted(drops.items(), key=lambda kv: kv[1]):
                current_value = current_scores.get(category)
                lines.append(f"  - {category}: {delta:+d} (now {current_value}/100)")

    return "\n".join(lines)


def send_webhook(webhook_url: str, target: str, current_scores: dict, trend: dict,
                  webhook_format: str = "slack", timeout: int = 10) -> dict:
    """Sends the notification. Returns {"success": bool, "error": str or None}."""
    if webhook_format == "slack":
        payload = {"text": format_slack_text(target, current_scores, trend)}
    else:
        payload = {"target": target, "scores": current_scores, "trend": trend}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            return {"success": False, "error": f"Webhook returned HTTP {resp.status_code}"}
        return {"success": True, "error": None}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}
