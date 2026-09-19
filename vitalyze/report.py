"""Aggregates per-category results into scores and exportable reports."""

import json
import time

from . import colors


def score(results: dict) -> dict:
    scores = {}

    # Response time score: <200ms avg = 100, >3000ms = 0, linear between
    rt = results.get("response_time", {})
    if rt.get("success"):
        avg = rt["total_time_ms"]["avg"]
        scores["response_time"] = _linear_score(avg, best=200, worst=3000)

    # SSL score
    ssl_res = results.get("ssl", {})
    if ssl_res.get("success"):
        s = 100
        if ssl_res.get("expiring_soon"):
            s -= 40
        if ssl_res.get("days_remaining", 0) < 0:
            s = 0
        scores["ssl"] = s
    elif "ssl" in results:
        scores["ssl"] = 0

    # Security headers score (already 0-100)
    headers = results.get("security_headers", {})
    if headers.get("success"):
        scores["security_headers"] = headers["score"]

    # SEO score: weighted checklist
    seo = results.get("seo", {})
    if seo.get("success"):
        checks = [
            bool(seo.get("title")),
            0 < seo.get("title_length", 0) <= 60,
            bool(seo.get("meta_description")),
            seo.get("h1_count") == 1,
            seo.get("has_viewport_meta"),
            seo.get("has_canonical"),
            seo.get("robots_txt_found"),
            seo.get("sitemap_xml_found"),
        ]
        scores["seo"] = round(sum(checks) / len(checks) * 100)

    # Caching score: advisory, not punitive — an intentional no-store on a
    # private page isn't a defect, so this rewards *having a deliberate
    # policy* (any Cache-Control/ETag/Last-Modified signal) over having none.
    cache = results.get("caching", {})
    if cache.get("success"):
        if cache.get("cache_control_raw"):
            scores["caching"] = 100 if cache.get("is_cacheable") else 70
        elif cache.get("etag") or cache.get("last_modified"):
            scores["caching"] = 80
        else:
            scores["caching"] = 40

    # Redirect score: fewer hops = better. A detected loop yields no score
    # (the failure is more informative reported as an error than a number).
    redir = results.get("redirects", {})
    if redir.get("success"):
        hop_penalty = {0: 0, 1: 10, 2: 25, 3: 40}.get(redir["hop_count"], 60)
        scores["redirects"] = max(0, 100 - hop_penalty)

    # Load test score (only if run)
    load = results.get("load_test")
    if load:
        error_penalty = load["error_rate_pct"]
        lat = load.get("latency_ms") or {}
        latency_score = _linear_score(lat.get("avg", 0) or 0, best=200, worst=3000)
        scores["load_handling"] = round(max(0, latency_score - error_penalty))

    if scores:
        scores["overall"] = round(sum(scores.values()) / len(scores))

    return scores


def grade(score_value) -> str:
    """Map a 0-100 score to a letter grade for a quicker read at a glance."""
    if score_value is None:
        return "N/A"
    if score_value >= 90:
        return "A"
    if score_value >= 80:
        return "B"
    if score_value >= 70:
        return "C"
    if score_value >= 60:
        return "D"
    return "F"


def _linear_score(value, best, worst):
    if value <= best:
        return 100
    if value >= worst:
        return 0
    return round(100 * (worst - value) / (worst - best))


def verdict(overall_score) -> str:
    """A plain-language read of the overall score, so a number doesn't have
    to speak for itself."""
    if overall_score is None:
        return "No scoreable results."
    if overall_score >= 90:
        return "Excellent — this is in great shape."
    if overall_score >= 80:
        return "Good — solid overall, a few things worth polishing."
    if overall_score >= 60:
        return "Fair — functional, but some real issues to address."
    if overall_score >= 40:
        return "Needs work — several categories need attention."
    return "Poor — significant issues across multiple categories."


def print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print(colors.bold("SUMMARY"))
    print("=" * 60)
    scores = results.get("scores", {})
    if not scores:
        print("No scoreable results.")
        return
    for category, value in scores.items():
        if category == "overall":
            continue
        color_fn = colors.color_for_score(value)
        bar = color_fn(_bar(value))
        print(f"  {category:<18} {bar} {color_fn(f'{value}/100')}  [{color_fn(grade(value))}]")
    print("-" * 60)
    overall = scores.get("overall", 0)
    color_fn = colors.color_for_score(overall)
    overall_label = colors.bold(f"{'OVERALL':<18}")  # pad before coloring, not after —
    # ANSI escape bytes count toward len() and would throw off :<N alignment otherwise
    print(f"  {overall_label} {color_fn(_bar(overall))} "
          f"{color_fn(f'{overall}/100')}  [{color_fn(grade(overall))}]")
    print("=" * 60)
    print(f"  {verdict(overall)}")
    print("=" * 60)


def _bar(value, width=20):
    filled = round((value / 100) * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def to_json(results: dict) -> str:
    return json.dumps(results, indent=2, default=str)


def to_html(results: dict) -> str:
    scores = results.get("scores", {})

    def badge_color(val):
        if val >= 80:
            return "#4ade80"
        if val >= 50:
            return "#facc15"
        return "#f87171"

    rows = "".join(
        f"<tr><td>{cat}</td>"
        f"<td><div class='bar'><div class='fill' style='width:{val}%; background:{badge_color(val)}'></div></div></td>"
        f"<td style='color:{badge_color(val)}'>{val}/100</td>"
        f"<td><span class='badge' style='background:{badge_color(val)}'>{grade(val)}</span></td></tr>"
        for cat, val in scores.items() if cat != "overall"
    )
    overall = scores.get("overall", "N/A")
    overall_grade = grade(overall) if isinstance(overall, int) else "N/A"
    overall_color = badge_color(overall) if isinstance(overall, int) else "#999"
    overall_verdict = verdict(overall) if isinstance(overall, int) else ""
    generated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(results.get("timestamp", time.time())))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Vitalyze Report - {results.get('host', '')}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #0f1115; color: #e6e6e6; padding: 2rem; max-width: 900px; margin: auto; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color: #999; margin-bottom: 2rem; }}
  .overall {{ font-size: 3rem; font-weight: bold; color: {overall_color}; }}
  .verdict {{ font-size: 1.1rem; color: #ccc; margin-top: 0.25rem; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
  td {{ padding: 0.6rem 0.4rem; border-bottom: 1px solid #262a33; }}
  .bar {{ background: #262a33; border-radius: 4px; height: 10px; width: 200px; overflow: hidden; }}
  .fill {{ height: 100%; transition: width 0.3s ease; }}
  .badge {{ display: inline-block; min-width: 1.6rem; text-align: center; padding: 0.1rem 0.5rem; border-radius: 6px; color: #0f1115; font-weight: bold; }}
  pre {{ background: #1a1d24; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; }}
</style>
</head>
<body>
  <h1>Vitalyze Report</h1>
  <div class="meta">Target: {results.get('target', '')} &middot; Generated: {generated}</div>
  <div class="overall">{overall}/100 <span style="font-size:1.2rem;">({overall_grade})</span></div>
  <div class="verdict">{overall_verdict}</div>
  <table>{rows}</table>
  <h2>Raw Results</h2>
  <pre>{json.dumps(results, indent=2, default=str)}</pre>
</body>
</html>"""
