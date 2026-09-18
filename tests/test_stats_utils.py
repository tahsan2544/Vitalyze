"""Tests for percentile/summary statistics helpers."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import stats_utils


def test_percentile_empty_returns_none():
    assert stats_utils.percentile([], 95) is None


def test_percentile_single_value():
    assert stats_utils.percentile([42], 95) == 42


def test_percentile_known_values():
    data = [10, 20, 30, 40, 50]
    assert stats_utils.percentile(data, 0) == 10
    assert stats_utils.percentile(data, 100) == 50
    assert stats_utils.percentile(data, 50) == 30


def test_summarize_empty_returns_none():
    assert stats_utils.summarize([]) is None


def test_summarize_single_value_stdev_zero():
    result = stats_utils.summarize([100])
    assert result["stdev"] == 0.0
    assert result["avg"] == 100
    assert result["min"] == result["max"] == 100


def test_summarize_has_all_expected_keys():
    result = stats_utils.summarize([10, 20, 30, 40, 50])
    for key in ("min", "max", "avg", "median", "p90", "p95", "p99", "stdev"):
        assert key in result


def test_summarize_stdev_nonzero_for_varied_data():
    result = stats_utils.summarize([10, 100, 10, 100])
    assert result["stdev"] > 0


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
