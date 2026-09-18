"""
Capped, rate-limited concurrent load test.

Safety notes (read before use):
- This module is for measuring how YOUR OWN site handles concurrent load,
  not for taking a site offline. It is deliberately capped and rate-limited.
- MAX_CONCURRENCY and MAX_REQUESTS are hard ceilings enforced regardless of
  CLI arguments. This tool does not scale beyond them, does not support
  distributed/multi-host execution, and does not target multiple hosts or
  subdomains in one run.
- Running concurrent traffic against infrastructure you do not own or lack
  explicit authorization to test may violate the law (e.g., the U.S. Computer
  Fraud and Abuse Act) and most hosting providers' terms of service. Only
  point this at domains you control or have written permission to test.
- For serious load testing, prefer a mature, purpose-built tool such as k6
  or Locust, which offer far better tooling for this than a hand-rolled
  script ever will.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from . import stats_utils

MAX_CONCURRENCY = 20
MAX_REQUESTS = 500


def _single_request(url: str, timeout: int) -> dict:
    start = time.perf_counter()
    try:
        resp = requests.get(url, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": True, "status": resp.status_code, "latency_ms": elapsed}
    except requests.exceptions.RequestException as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "error": str(e), "latency_ms": elapsed}


def run(url: str, concurrency: int = 5, total_requests: int = 50, timeout: int = 15) -> dict:
    concurrency = min(max(concurrency, 1), MAX_CONCURRENCY)
    total_requests = min(max(total_requests, 1), MAX_REQUESTS)

    latencies = []
    statuses = []
    errors = []

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_single_request, url, timeout) for _ in range(total_requests)]
        for future in as_completed(futures):
            res = future.result()
            latencies.append(res["latency_ms"])
            if res["ok"]:
                statuses.append(res["status"])
            else:
                errors.append(res["error"])
    wall_time = time.perf_counter() - start_time

    success_count = len(statuses)
    error_count = len(errors)

    result = {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "wall_time_sec": round(wall_time, 2),
        "requests_per_sec": round(total_requests / wall_time, 2) if wall_time > 0 else None,
        "success_count": success_count,
        "error_count": error_count,
        "error_rate_pct": round((error_count / total_requests) * 100, 2),
        "status_code_distribution": _distribution(statuses),
        "latency_ms": stats_utils.summarize(latencies),
        "sample_errors": list(set(errors))[:5],
    }
    return result


def _distribution(statuses):
    dist = {}
    for s in statuses:
        dist[str(s)] = dist.get(str(s), 0) + 1
    return dist


def print_result(result: dict) -> None:
    lat = result["latency_ms"]
    print(f"    Requests sent:     {result['total_requests']} @ concurrency {result['concurrency']}")
    print(f"    Wall time:         {result['wall_time_sec']}s ({result['requests_per_sec']} req/s)")
    print(f"    Success/Error:     {result['success_count']}/{result['error_count']} "
          f"({result['error_rate_pct']}% error rate)")
    print(f"    Status codes:      {result['status_code_distribution']}")
    if lat:
        print(f"    Latency (ms):      avg={lat['avg']} median={lat['median']} "
              f"p90={lat['p90']} p95={lat['p95']} p99={lat['p99']} "
              f"max={lat['max']} stdev={lat['stdev']}")
        if lat["stdev"] > lat["avg"] * 0.5 and lat["avg"] > 0:
            print("    [!] High latency variance (stdev > 50% of avg) — inconsistent response times under load")
    if result["sample_errors"]:
        print(f"    Sample errors:     {result['sample_errors']}")
