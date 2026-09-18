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
from vitalyze import load_test
from vitalyze import report
from vitalyze import __version__

BANNER = r"""
========================================
   V I T A L Y Z E
   Website Performance & Health Analyzer
========================================
"""

ALL_CATEGORIES = ["dns", "redirects", "response", "ssl", "headers", "caching", "seo"]


def normalize_url(raw: str) -> str:
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vitalyze - measure a website's performance and health across categories.",
        epilog="Only run this against domains you own or are explicitly authorized to test.",
    )
    parser.add_argument("url", help="Target URL, e.g. https://example.com")
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
    return parser


def main():
    args = build_arg_parser().parse_args()
    target = normalize_url(args.url)
    parsed = urlparse(target)

    if not parsed.netloc:
        print(f"[!] Could not parse a valid host from: {args.url}")
        sys.exit(1)

    console = args.output == "console"

    if console:
        print(BANNER)
        print(f"Target: {target}")
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

    if console:
        report.print_summary(results)
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
