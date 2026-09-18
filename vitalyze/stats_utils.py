"""Shared statistical helpers used across timing and load-test modules.

Centralized so every numeric sample set (response phases, load-test
latencies) is reported with the same level of precision: min/max/avg/median
plus p90/p95/p99 and standard deviation, instead of just a bare average.
"""

import statistics


def percentile(data, pct):
    """Linear-interpolation percentile (same method as numpy's default)."""
    if not data:
        return None
    sorted_data = sorted(data)
    if len(sorted_data) == 1:
        return sorted_data[0]
    k = (len(sorted_data) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def summarize(data, ndigits=2):
    """Full spread summary for a list of numeric samples, or None if empty.

    Returns min/max/avg/median/p90/p95/p99/stdev — stdev is 0.0 for a
    single sample (no spread to measure) rather than undefined.
    """
    if not data:
        return None
    result = {
        "min": round(min(data), ndigits),
        "max": round(max(data), ndigits),
        "avg": round(statistics.mean(data), ndigits),
        "median": round(statistics.median(data), ndigits),
        "p90": round(percentile(data, 90), ndigits),
        "p95": round(percentile(data, 95), ndigits),
        "p99": round(percentile(data, 99), ndigits),
        "stdev": round(statistics.stdev(data), ndigits) if len(data) > 1 else 0.0,
    }
    return result
