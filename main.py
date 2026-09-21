#!/usr/bin/env python3
"""
Vitalyze - Website Performance & Health Analyzer
===================================================
CLI entry point. Orchestrates DNS, redirect chain, response time, SSL,
security headers, caching, SEO, and (opt-in) load tests against a single
target you own or are authorized to test.

Redirects are resolved first: response time, SSL, headers, caching, and SEO
are all measured against the final destination URL, not an intermediate
redirect hop, so a "http:// -> https://" or "bare domain -> www" redirect
doesn't get measured as if the 301 itself were the page.

Usage:
    python main.py https://example.com
    python main.py https://example.com --load-test --confirm-authorized
    python main.py https://example.com --output json --save report.json
    python main.py https://example.com --output html --save report.html
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import urlparse

from vitalyze import dns_check
from vitalyze import redirects
from vitalyze import response_time
from vitalyze import ssl_check
from vitalyze import security_headers
from vitalyze import caching
from vitalyze import seo_basics
from vitalyze import mixed_content
from vitalyze import social_meta
from vitalyze import accessibility
from vitalyze import load_test
from vitalyze import report
from vitalyze import config as config_module
from vitalyze import history
from vitalyze import alerts
from vitalyze import colors
from vitalyze import __version__

BANNER = r"""
========================================
   V I T A L Y Z E
   Website Performance & Health Analyzer
========================================
"""

ALL_CATEGORIES = [
    "dns", "redirects", "response", "ssl", "headers", "caching", "seo",
    "mixed_content", "social", "accessibility",
]


def normalize_url(raw: str) -> str:
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vitalyze - measure a website's performance and health across categories.",
        epilog="Only run this against domains you own or are explicitly authorized to test.",
    )
    parser.add_argument("url", nargs="?", default=None,
                         help="Target URL, e.g. https://example.com (optional if set in --config)")
    parser.add_argument("--config", metavar="FILE",
                         help=f"Load settings from a JSON config file (default: ./{config_module.DEFAULT_CONFIG_FILENAME} if present)")
    parser.add_argument("--save-config", metavar="FILE",
                         help="Save this run's settings to a JSON config file for reuse")
    parser.add_argument("--version", action="version", version=f"Vitalyze {__version__}")
    parser.add_argument(
        "--runs", type=int, default=5,
        help="Number of requests to average for response-time stats (default: 5)"
    )
    parser.add_argument(
        "--skip", nargs="*", default=[],
        choices=ALL_CATEGORIES,
        help="Skip specific check categories"
    )
    parser.add_argument(
        "--load-test", action="store_true",
        help="Also run a capped, rate-limited load test (requires --confirm-authorized)"
    )
    parser.add_argument(
        "--confirm-authorized", action="store_true",
        help="Required alongside --load-test: confirms you own/are authorized to test this target"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Load test: concurrent workers, hard-capped at 20 (default: 5)"
    )
    parser.add_argument(
        "--requests", type=int, default=50,
        help="Load test: total requests to send, hard-capped at 500 (default: 50)"
    )
    parser.add_argument(
        "--output", choices=["console", "json", "html"], default="console",
        help="Output format (default: console)"
    )
    parser.add_argument(
        "--save", metavar="FILE",
        help="Save output to a file (used with --output json/html)"
    )
    parser.add_argument(
        "--history-db", metavar="FILE", default=history.DEFAULT_HISTORY_DB_FILENAME,
        help=f"SQLite file for run history (default: ./{history.DEFAULT_HISTORY_DB_FILENAME})"
    )
    parser.add_argument(
        "--no-history", action="store_true",
        help="Don't record this run's scores to history"
    )
    parser.add_argument(
        "--trend", action="store_true",
        help="Compare this run's scores against the most recent previous run for this target"
    )
    parser.add_argument(
        "--show-history", nargs="?", const=10, type=int, default=None, metavar="N",
        help="Show the last N historical runs for this target (default 10) and exit without scanning"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored output (also auto-disabled when piping to a file, or via the NO_COLOR env var)"
    )
    parser.add_argument(
        "--webhook", metavar="URL",
        help="Send a notification to this webhook URL when the score regresses (requires history)"
    )
    parser.add_argument(
        "--webhook-format", choices=["slack", "generic"], default="slack",
        help="Payload shape for --webhook: 'slack' for Slack-compatible {text}, 'generic' for raw JSON (default: slack)"
    )
    parser.add_argument(
        "--alert-threshold", type=int, default=10, metavar="N",
        help="Minimum point drop (overall or any category) to trigger a --webhook alert (default: 10)"
    )
    parser.add_argument(
        "--alert-always", action="store_true",
        help="Send the --webhook notification every run, not only on a regression"
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # --- Config file: load and apply as defaults, then re-parse so any
    # flag actually typed on the command line still wins over the config ---
    config_path = args.config or (
        config_module.DEFAULT_CONFIG_FILENAME
        if os.path.isfile(config_module.DEFAULT_CONFIG_FILENAME) else None
    )
    if config_path:
        try:
            config_data = config_module.load(config_path)
        except ValueError as e:
            print(f"[!] {e}")
            sys.exit(1)
        if config_data:
            parser.set_defaults(**config_data)
            args = parser.parse_args()  # re-parse: CLI flags override config defaults

    if not args.url:
        print("[!] No URL given on the command line or in a config file.")
        sys.exit(1)

    if args.skip:
        invalid = set(args.skip) - set(ALL_CATEGORIES)
        if invalid:
            print(f"[!] Invalid --skip categories: {', '.join(sorted(invalid))}")
            sys.exit(1)
    if args.output not in ("console", "json", "html"):
        print(f"[!] Invalid --output value: {args.output}")
        sys.exit(1)

    console = args.output == "console"
    if args.no_color or not console:
        colors.disable()

    if args.save_config:
        config_module.save(args.save_config, vars(args))
        if args.output == "console":
            print(f"[+] Settings saved to {args.save_config}")
            if args.webhook:
                warning = ("Your config file now contains a webhook URL. Slack/webhook URLs "
                            "act like a password — don't commit this file to a public repo.")
                print(f"    {colors.warn(warning)}")

    target = normalize_url(args.url)
    parsed = urlparse(target)

    if not parsed.netloc:
        print(f"[!] Could not parse a valid host from: {args.url}")
        sys.exit(1)

    if console:
        print(BANNER)
        print(f"Target: {target}")

    # --- History query mode: show past runs and exit, no scan performed ---
    if args.show_history is not None:
        records = history.fetch_history(args.history_db, target, limit=args.show_history)
        if console:
            history.print_history_table(records, target)
        elif args.output == "json":
            print(json.dumps({"target": target, "history": records}, indent=2))
        else:
            print("[!] --show-history only supports --output console or json")
        sys.exit(0)

    if console:
        print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)

    results = {"target": target, "host": parsed.netloc, "timestamp": time.time()}
    step = 1

    # --- DNS ---
    if "dns" not in args.skip:
        if console:
            print(f"\n[{step}] DNS Resolution")
        results["dns"] = dns_check.run(parsed.netloc)
        if console:
            dns_check.print_result(results["dns"])
        step += 1

    # --- Redirect chain (resolves the URL every later check analyzes) ---
    analysis_url = target
    if "redirects" not in args.skip:
        if console:
            print(f"\n[{step}] Redirect Chain")
        redirect_result = redirects.run(target)
        results["redirects"] = redirect_result
        if console:
            redirects.print_result(redirect_result)
        if redirect_result.get("success") and redirect_result.get("final_url"):
            analysis_url = redirect_result["final_url"]
        step += 1

    analysis_parsed = urlparse(analysis_url)

    # --- Response time (phase-level: DNS/TCP/TLS/TTFB/download) ---
    if "response" not in args.skip:
        if console:
            print(f"\n[{step}] Response Time")
        results["response_time"] = response_time.run(analysis_url, runs=args.runs)
        if console:
            response_time.print_result(results["response_time"])
        step += 1

    # --- SSL/TLS (against the final destination host) ---
    if "ssl" not in args.skip and analysis_parsed.scheme == "https":
        if console:
            print(f"\n[{step}] SSL/TLS Certificate")
        results["ssl"] = ssl_check.run(analysis_parsed.netloc)
        if console:
            ssl_check.print_result(results["ssl"])
        step += 1

    # --- Security headers ---
    if "headers" not in args.skip:
        if console:
            print(f"\n[{step}] Security Headers")
        results["security_headers"] = security_headers.run(analysis_url)
        if console:
            security_headers.print_result(results["security_headers"])
        step += 1

    # --- Caching ---
    if "caching" not in args.skip:
        if console:
            print(f"\n[{step}] Caching")
        results["caching"] = caching.run(analysis_url)
        if console:
            caching.print_result(results["caching"])
        step += 1

    # --- SEO basics ---
    if "seo" not in args.skip:
        if console:
            print(f"\n[{step}] SEO Basics")
        results["seo"] = seo_basics.run(analysis_url)
        if console:
            seo_basics.print_result(results["seo"])
        step += 1

    # --- Mixed content (HTTP resources on an HTTPS page) ---
    if "mixed_content" not in args.skip:
        if console:
            print(f"\n[{step}] Mixed Content")
        results["mixed_content"] = mixed_content.run(analysis_url)
        if console:
            mixed_content.print_result(results["mixed_content"])
        step += 1

    # --- Social meta tags (Open Graph / Twitter Card) — informational only ---
    if "social" not in args.skip:
        if console:
            print(f"\n[{step}] Social Meta Tags")
        results["social"] = social_meta.run(analysis_url)
        if console:
            social_meta.print_result(results["social"])
        step += 1

    # --- Accessibility basics ---
    if "accessibility" not in args.skip:
        if console:
            print(f"\n[{step}] Accessibility")
        results["accessibility"] = accessibility.run(analysis_url)
        if console:
            accessibility.print_result(results["accessibility"])
        step += 1

    # --- Load test (opt-in, gated; hits the original target, redirects included) ---
    if args.load_test:
        if not args.confirm_authorized:
            print(
                "\n[!] --load-test requires --confirm-authorized.\n"
                "    This confirms you own the target or have explicit written\n"
                "    permission to run concurrent traffic against it.\n"
                "    Example: python main.py https://yoursite.com --load-test --confirm-authorized"
            )
            sys.exit(1)

        concurrency = min(max(args.concurrency, 1), load_test.MAX_CONCURRENCY)
        total_requests = min(max(args.requests, 1), load_test.MAX_REQUESTS)

        if console:
            print(f"\n[{step}] Load Test (capped, rate-limited)")
            print(f"    concurrency={concurrency}, total_requests={total_requests}")
        results["load_test"] = load_test.run(
            target, concurrency=concurrency, total_requests=total_requests
        )
        if console:
            load_test.print_result(results["load_test"])
        step += 1

    # --- Scoring + report ---
    results["scores"] = report.score(results)

    # --- Trend: fetch the previous run BEFORE recording this one, or
    # comparing a run against itself is impossible to avoid. Needed both
    # for --trend display and for --webhook's regression check. ---
    if args.trend or args.webhook:
        previous = history.previous_run(args.history_db, target)
        if previous:
            results["trend"] = history.compute_deltas(previous["scores"], results["scores"])
            results["trend_previous_timestamp"] = previous["timestamp"]
        else:
            results["trend"] = None
            results["trend_previous_timestamp"] = None

    if not args.no_history:
        history.record(args.history_db, target, parsed.netloc, results["timestamp"], results["scores"])

    # --- Webhook alert: only fires on a real regression unless --alert-always ---
    if args.webhook:
        trend = results.get("trend")
        triggered = args.alert_always or alerts.should_alert(trend, args.alert_threshold)
        results["webhook"] = {"attempted": triggered, "success": None, "error": None}
        if triggered:
            outcome = alerts.send_webhook(
                args.webhook, target, results["scores"], trend, webhook_format=args.webhook_format
            )
            results["webhook"]["success"] = outcome["success"]
            results["webhook"]["error"] = outcome["error"]

    if console:
        report.print_summary(results)
        if args.trend:
            print()
            history.print_trend(results.get("trend"), results.get("trend_previous_timestamp"))
        if args.webhook and results["webhook"]["attempted"]:
            if results["webhook"]["success"]:
                print(f"\n{colors.ok('Webhook notification sent')}")
            else:
                message = f"Webhook notification failed: {results['webhook']['error']}"
                print(f"\n{colors.warn(message)}")
    elif args.output == "json":
        out = report.to_json(results)
        if args.save:
            with open(args.save, "w") as f:
                f.write(out)
            print(f"[+] JSON report saved to {args.save}")
        else:
            print(out)
    elif args.output == "html":
        out = report.to_html(results)
        path = args.save or "vitalyze_report.html"
        with open(path, "w") as f:
            f.write(out)
        print(f"[+] HTML report saved to {path}")


if __name__ == "__main__":
    main()
