"""Basic unit tests for scoring logic. Run with: python -m pytest tests/"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import report


def test_linear_score_best_case():
    assert report._linear_score(100, best=200, worst=3000) == 100


def test_linear_score_worst_case():
    assert report._linear_score(5000, best=200, worst=3000) == 0


def test_linear_score_midpoint():
    score = report._linear_score(1600, best=200, worst=3000)
    assert 40 <= score <= 60


def test_score_with_no_data_returns_empty():
    result = report.score({})
    assert result == {}


def test_score_ssl_expiring_soon_penalized():
    results = {
        "ssl": {
            "success": True,
            "expiring_soon": True,
            "days_remaining": 15,
        }
    }
    scores = report.score(results)
    assert scores["ssl"] == 60


def test_score_ssl_healthy():
    results = {
        "ssl": {
            "success": True,
            "expiring_soon": False,
            "days_remaining": 200,
        }
    }
    scores = report.score(results)
    assert scores["ssl"] == 100


def test_overall_is_average_of_categories():
    results = {
        "ssl": {"success": True, "expiring_soon": False, "days_remaining": 200},
        "security_headers": {"success": True, "score": 50},
    }
    scores = report.score(results)
    assert scores["overall"] == round((100 + 50) / 2)


def test_caching_score_deliberate_policy_scores_full():
    results = {"caching": {"success": True, "cache_control_raw": "public, max-age=3600", "is_cacheable": True}}
    assert report.score(results)["caching"] == 100


def test_caching_score_deliberate_no_store_not_penalized_as_missing():
    results = {"caching": {"success": True, "cache_control_raw": "no-store", "is_cacheable": False}}
    assert report.score(results)["caching"] == 70


def test_caching_score_validator_only():
    results = {"caching": {"success": True, "cache_control_raw": None, "etag": '"x"', "last_modified": None}}
    assert report.score(results)["caching"] == 80


def test_caching_score_no_signals_at_all():
    results = {"caching": {"success": True, "cache_control_raw": None, "etag": None, "last_modified": None}}
    assert report.score(results)["caching"] == 40


def test_redirects_score_no_hops_is_perfect():
    results = {"redirects": {"success": True, "hop_count": 0}}
    assert report.score(results)["redirects"] == 100


def test_redirects_score_penalizes_many_hops():
    results = {"redirects": {"success": True, "hop_count": 5}}
    assert report.score(results)["redirects"] == 40


def test_load_test_score_handles_all_requests_failed():
    """latency_ms is None when every request in the load test failed —
    scoring must not crash trying to read .get('avg') off None."""
    results = {"load_test": {"error_rate_pct": 100.0, "latency_ms": None}}
    scores = report.score(results)
    assert scores["load_handling"] == 0


def test_grade_boundaries():
    assert report.grade(90) == "A"
    assert report.grade(89) == "B"
    assert report.grade(80) == "B"
    assert report.grade(70) == "C"
    assert report.grade(60) == "D"
    assert report.grade(59) == "F"
    assert report.grade(None) == "N/A"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
