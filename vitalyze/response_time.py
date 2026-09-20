"""Measures response time as separate phases (DNS, TCP connect, TLS handshake,
TTFB, download) over multiple runs, with percentile and spread statistics —
not just a single averaged total.

Also measures connection-reuse ("warm") timing alongside the main cold-
connection-per-request numbers: every phase measurement above forces a
fresh TCP+TLS handshake per request (Connection: close), which is a real,
useful "worst case first visit" number — but a browser reusing a
connection for a second page view or another resource on the same host
sees something faster. Both numbers are reported; neither alone is the
whole picture.
"""

import statistics

from . import timing
from . import stats_utils
from . import colors


def run(url: str, runs: int = 5, timeout: int = 15) -> dict:
    dns_samples, tcp_samples, tls_samples = [], [], []
    ttfb_samples, download_samples, total_samples = [], [], []
    status_codes = []
    sizes = []
    errors = []
    http_version = None
    content_encoding = None

    for _ in range(max(1, runs)):
        res = timing.single_request(url, timeout=timeout)
        if not res.get("success"):
            errors.append(res.get("error", "unknown error"))
            continue

        dns_samples.append(res["dns_ms"])
        tcp_samples.append(res["tcp_connect_ms"])
        if res["tls_handshake_ms"] is not None:
            tls_samples.append(res["tls_handshake_ms"])
        ttfb_samples.append(res["ttfb_ms"])
        download_samples.append(res["download_ms"])
        total_samples.append(res["total_ms"])
        status_codes.append(res["status_code"])
        sizes.append(res["content_length"])
        http_version = res["http_version"]
        content_encoding = res["content_encoding"] or content_encoding

    if not total_samples:
        return {"success": False, "errors": errors, "warm": _measure_warm(url, runs, timeout)}

    return {
        "success": True,
        "runs_completed": len(total_samples),
        "runs_failed": len(errors),
        "status_codes": status_codes,
        "http_version": http_version,
        "content_encoding": content_encoding,
        "avg_page_size_bytes": round(statistics.mean(sizes)),
        "phases_ms": {
            "dns": stats_utils.summarize(dns_samples),
            "tcp_connect": stats_utils.summarize(tcp_samples),
            "tls_handshake": stats_utils.summarize(tls_samples) if tls_samples else None,
            "ttfb": stats_utils.summarize(ttfb_samples),
            "download": stats_utils.summarize(download_samples),
        },
        "total_time_ms": stats_utils.summarize(total_samples),
        "errors": errors,
        "warm": _measure_warm(url, runs, timeout),
    }


def _measure_warm(url: str, runs: int, timeout: int) -> dict:
    """Connection-reuse (HTTP keep-alive) timing — see module docstring.
    Failure here never fails the overall check; it's supplementary context."""
    session_results = timing.run_session(url, runs=runs, timeout=timeout)
    successful = [r for r in session_results if r.get("success")]

    if not successful:
        error = session_results[0].get("error") if session_results else "unknown error"
        return {"success": False, "note": f"Connection-reuse measurement failed: {error}"}

    cold_entry = next((r for r in successful if not r["warm"]), None)
    warm_entries = [r for r in successful if r["warm"]]

    return {
        "success": True,
        "requests_reused": len(warm_entries),
        "first_request_total_ms": cold_entry["total_ms"] if cold_entry else None,
        "warm_total_ms": stats_utils.summarize([r["total_ms"] for r in warm_entries]) if warm_entries else None,
        "note": (
            "First request pays full DNS+TCP+TLS setup; the rest reuse that "
            "same connection (HTTP keep-alive) — closer to how a browser "
            "experiences a repeat request to the same host."
        ),
    }


def print_result(result: dict) -> None:
    if not result.get("success"):
        message = f"All requests failed: {result.get('errors')}"
        print(f"    {colors.bad(message)}")
        warm = result.get("warm")
        if warm and warm.get("success"):
            note = "Connection-reuse check succeeded independently — the target may be reachable but rejecting Connection: close requests specifically."
            print(f"    {colors.dim(note)}")
        return

    print(f"    Runs completed:   {result['runs_completed']} (failed: {result['runs_failed']})")
    print(f"    Status codes:     {result['status_codes']}")
    print(f"    HTTP version:     {result['http_version']}")
    print(f"    Compression:      {result['content_encoding'] or 'none detected'}")
    print(f"    Avg page size:    {result['avg_page_size_bytes'] / 1024:.1f} KB")

    print("\n    Phase breakdown (ms) — fresh connection per request:")
    phases = result["phases_ms"]
    labels = {
        "dns": "DNS lookup",
        "tcp_connect": "TCP connect",
        "tls_handshake": "TLS handshake",
        "ttfb": "Time to first byte",
        "download": "Download",
    }
    for key, label in labels.items():
        s = phases.get(key)
        if s is None:
            continue
        print(f"      {label:<20} avg={s['avg']:<8} median={s['median']:<8} "
              f"p95={s['p95']:<8} stdev={s['stdev']}")

    tt = result["total_time_ms"]
    print(f"\n    Total time (ms):  avg={tt['avg']} median={tt['median']} "
          f"p90={tt['p90']} p95={tt['p95']} p99={tt['p99']} stdev={tt['stdev']}")

    warm = result.get("warm")
    if warm and warm.get("success") and warm["requests_reused"] > 0:
        wt = warm["warm_total_ms"]
        cold_total = warm["first_request_total_ms"]
        print("\n    Connection reuse (warm, HTTP keep-alive):")
        print(f"      First request (cold):   {cold_total} ms — full DNS+TCP+TLS setup")
        print(f"      Reused requests (warm): avg={wt['avg']} median={wt['median']} "
              f"p95={wt['p95']} (n={warm['requests_reused']})")
        if cold_total and wt["avg"] and wt["avg"] > 0:
            speedup = cold_total / wt["avg"]
            if speedup > 1.1:
                message = (f"{speedup:.1f}x faster once the connection is already open — "
                           "the numbers above reflect a fresh-connection worst case, not a typical repeat visit")
                print(f"      {colors.dim('note: ' + message)}")
    elif warm and not warm.get("success"):
        print(f"\n    {colors.dim(warm.get('note', 'Connection-reuse measurement unavailable'))}")
