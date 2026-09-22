"""
Capped, rate-limited concurrent load test.

Safety notes (read before use):
- This module is for measuring how YOUR OWN site handles concurrent load,
  not for taking a site offline. It is deliberately capped and rate-limited.
- MAX_CONCURRENCY, MAX_REQUESTS, MAX_DURATION_SECONDS, and MAX_RAMP_UP_SECONDS
  are hard ceilings enforced regardless of CLI arguments. This tool does not
  scale beyond them, does not support distributed/multi-host execution, and
  does not target multiple hosts or subdomains in one run.
- Auto-abort (see abort_threshold_pct) is a genuine safety feature, not
  window dressing: if the target's error rate spikes, this stops sending
  traffic rather than continuing to hammer a server that may already be
  struggling or down.
- Running concurrent traffic against infrastructure you do not own or lack
  explicit authorization to test may violate the law (e.g., the U.S. Computer
  Fraud and Abuse Act) and most hosting providers' terms of service. Only
  point this at domains you control or have written permission to test.
- For serious load testing, prefer a mature, purpose-built tool such as k6
  or Locust, which offer far better tooling for this than a hand-rolled
  script ever will.

Design notes:
- Each of the `concurrency` worker threads keeps its own requests.Session
  (via threading.local), so connections are reused within a worker across
  its requests — simulating `concurrency` persistent concurrent users, not
  `concurrency` threads each paying a fresh TCP+TLS handshake on every
  single request. The old version did the latter, which both understated
  real throughput and measured something other than what it claimed to.
- Two modes: a fixed request count (`total_requests`), or a fixed wall-clock
  duration (`duration_seconds`) — workers loop until the shared deadline
  instead of pulling from a queue.
- Ramp-up staggers each worker's start time evenly across the ramp window,
  so concurrency grows gradually instead of hitting the target instantly.
"""

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from . import stats_utils
from . import colors

MAX_CONCURRENCY = 20
MAX_REQUESTS = 500
MAX_DURATION_SECONDS = 60
MAX_RAMP_UP_SECONDS = 30
MIN_REQUESTS_BEFORE_ABORT_CHECK = 10

_thread_local = threading.local()


def _get_session() -> requests.Session:
    """One persistent Session per worker thread, reused across that
    worker's requests for the life of the run."""
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
    return _thread_local.session


def _single_request(url: str, timeout: int) -> dict:
    session = _get_session()
    start = time.perf_counter()
    try:
        resp = session.get(url, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": True, "status": resp.status_code, "latency_ms": elapsed}
    except requests.exceptions.RequestException as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "error": str(e), "latency_ms": elapsed}


def _stagger_delay(worker_index: int, concurrency: int, ramp_up_seconds: float) -> float:
    """Spreads worker start times evenly across the ramp-up window, so
    concurrency grows gradually instead of hitting the target instantly.
    Pure function — no timing/threading involved, deterministically testable."""
    if ramp_up_seconds <= 0 or concurrency <= 1:
        return 0.0
    return (worker_index / concurrency) * ramp_up_seconds


def _check_abort(results_list: list, abort_threshold_pct) -> str:
    """Returns an abort reason string if the error rate has crossed the
    threshold, or None otherwise. Pure function operating on a snapshot
    list — deterministically testable without any real threading."""
    if abort_threshold_pct is None:
        return None
    if len(results_list) < MIN_REQUESTS_BEFORE_ABORT_CHECK:
        return None
    errors = sum(1 for r in results_list if not r["ok"])
    error_pct = errors / len(results_list) * 100
    if error_pct >= abort_threshold_pct:
        return (f"error rate {error_pct:.0f}% reached the {abort_threshold_pct}% "
                f"abort threshold after {len(results_list)} requests")
    return None


def run(url: str, concurrency: int = 5, total_requests: int = 50, timeout: int = 15,
        duration_seconds=None, ramp_up_seconds: float = 0, abort_threshold_pct=None) -> dict:
    concurrency = min(max(concurrency, 1), MAX_CONCURRENCY)
    ramp_up_seconds = min(max(ramp_up_seconds, 0), MAX_RAMP_UP_SECONDS)
    mode = "duration" if duration_seconds is not None else "count"

    work_queue = None
    if mode == "duration":
        # Floor at a small positive value (not a full second) — a legitimate
        # short health-check-style burst (e.g. 0.5s) shouldn't get silently
        # rounded up to a full second.
        duration_seconds = min(max(duration_seconds, 0.1), MAX_DURATION_SECONDS)
    else:
        total_requests = min(max(total_requests, 1), MAX_REQUESTS)
        work_queue = queue.Queue()
        for _ in range(total_requests):
            work_queue.put(1)

    results_list = []
    lock = threading.Lock()
    abort_event = threading.Event()
    abort_reason = {"text": None}

    def record(res):
        with lock:
            results_list.append(res)
            if not abort_event.is_set():
                reason = _check_abort(results_list, abort_threshold_pct)
                if reason:
                    abort_reason["text"] = reason
                    abort_event.set()

    start_time = time.perf_counter()
    deadline = start_time + duration_seconds if mode == "duration" else None

    def worker(worker_index):
        delay = _stagger_delay(worker_index, concurrency, ramp_up_seconds)
        if delay > 0:
            time.sleep(delay)

        if mode == "duration":
            while not abort_event.is_set() and time.perf_counter() < deadline:
                record(_single_request(url, timeout))
        else:
            while not abort_event.is_set():
                try:
                    work_queue.get_nowait()
                except queue.Empty:
                    return
                record(_single_request(url, timeout))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker, i) for i in range(concurrency)]
        for f in futures:
            f.result()

    wall_time = time.perf_counter() - start_time

    latencies = [r["latency_ms"] for r in results_list]
    statuses = [r["status"] for r in results_list if r["ok"]]
    errors = [r["error"] for r in results_list if not r["ok"]]
    sent = len(results_list)

    result = {
        "mode": mode,
        "concurrency": concurrency,
        "ramp_up_seconds": ramp_up_seconds,
        "total_requests": sent,
        "requested_total": total_requests if mode == "count" else None,
        "requested_duration_sec": duration_seconds if mode == "duration" else None,
        "wall_time_sec": round(wall_time, 2),
        "requests_per_sec": round(sent / wall_time, 2) if wall_time > 0 else None,
        "success_count": len(statuses),
        "error_count": len(errors),
        "error_rate_pct": round((len(errors) / sent) * 100, 2) if sent > 0 else 0.0,
        "status_code_distribution": _distribution(statuses),
        "latency_ms": stats_utils.summarize(latencies),
        "sample_errors": list(set(errors))[:5],
        "aborted_early": abort_event.is_set(),
        "abort_reason": abort_reason["text"],
    }
    return result


def _distribution(statuses):
    dist = {}
    for s in statuses:
        dist[str(s)] = dist.get(str(s), 0) + 1
    return dist


def print_result(result: dict) -> None:
    mode_label = (f"duration {result['requested_duration_sec']}s"
                  if result["mode"] == "duration" else f"{result['requested_total']} requests")
    ramp_note = f", ramp-up {result['ramp_up_seconds']}s" if result["ramp_up_seconds"] > 0 else ""
    print(f"    Mode:              {mode_label} @ concurrency {result['concurrency']}{ramp_note}")

    if result["aborted_early"]:
        message = f"Aborted early — {result['abort_reason']}"
        print(f"    {colors.bad(message)}")

    print(f"    Requests sent:     {result['total_requests']}")
    print(f"    Wall time:         {result['wall_time_sec']}s ({result['requests_per_sec']} req/s)")

    lat = result["latency_ms"]
    success_line = f"{result['success_count']}/{result['error_count']} ({result['error_rate_pct']}% error rate)"
    color_fn = colors.color_for_score(round(100 - result["error_rate_pct"]))
    print(f"    Success/Error:     {color_fn(success_line)}")
    print(f"    Status codes:      {result['status_code_distribution']}")
    if lat:
        print(f"    Latency (ms):      avg={lat['avg']} median={lat['median']} "
              f"p90={lat['p90']} p95={lat['p95']} p99={lat['p99']} "
              f"max={lat['max']} stdev={lat['stdev']}")
        if lat["stdev"] > lat["avg"] * 0.5 and lat["avg"] > 0:
            message = "High latency variance (stdev > 50% of avg) — inconsistent response times under load"
            print(f"    {colors.warn(message)}")
    if result["sample_errors"]:
        print(f"    Sample errors:     {result['sample_errors']}")
