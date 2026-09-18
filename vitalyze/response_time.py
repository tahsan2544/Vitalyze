"""Measures response time as separate phases (DNS, TCP connect, TLS handshake,
TTFB, download) over multiple runs, with percentile and spread statistics —
not just a single averaged total."""

import statistics

from . import timing
from . import stats_utils


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
        return {"success": False, "errors": errors}

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
    }


def print_result(result: dict) -> None:
    if not result.get("success"):
        print(f"    [x] All requests failed: {result.get('errors')}")
        return

    print(f"    Runs completed:   {result['runs_completed']} (failed: {result['runs_failed']})")
    print(f"    Status codes:     {result['status_codes']}")
    print(f"    HTTP version:     {result['http_version']}")
    print(f"    Compression:      {result['content_encoding'] or 'none detected'}")
    print(f"    Avg page size:    {result['avg_page_size_bytes'] / 1024:.1f} KB")

    print("\n    Phase breakdown (ms):")
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
