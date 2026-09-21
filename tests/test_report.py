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


def test_mixed_content_score_clean_page():
    results = {"mixed_content": {"success": True, "applicable": True, "mixed_count": 0}}
    assert report.score(results)["mixed_content"] == 100


def test_mixed_content_score_penalized_per_resource():
    results = {"mixed_content": {"success": True, "applicable": True, "mixed_count": 3}}
    assert report.score(results)["mixed_content"] == 40  # 100 - 3*20


def test_mixed_content_not_scored_when_not_applicable():
    """An HTTP page (mixed content doesn't apply) should get no score at
    all, not a misleading 100 or 0."""
    results = {"mixed_content": {"success": True, "applicable": False}}
    assert "mixed_content" not in report.score(results)


def test_accessibility_score_full_lang_and_alt():
    results = {"accessibility": {"success": True, "has_lang_attribute": True, "alt_text_coverage_pct": 100}}
    assert report.score(results)["accessibility"] == 100


def test_accessibility_score_missing_lang_averages_down():
    results = {"accessibility": {"success": True, "has_lang_attribute": False, "alt_text_coverage_pct": 100}}
    assert report.score(results)["accessibility"] == 50  # (0 + 100) / 2


def test_social_meta_never_contributes_a_score():
    """Deliberate design choice — see social_meta.py's docstring."""
    results = {"social": {"success": True, "has_basic_og": False, "has_twitter_card": False}}
    scores = report.score(results)
    assert "social" not in scores


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


def test_verdict_thresholds():
    assert "Excellent" in report.verdict(95)
    assert "Good" in report.verdict(85)
    assert "Fair" in report.verdict(65)
    assert "Needs work" in report.verdict(45)
    assert "Poor" in report.verdict(20)
    assert "No scoreable" in report.verdict(None)


def test_print_summary_bars_align_with_colors_enabled():
    """ANSI escape codes count toward len() — a naive f-string padding
    applied AFTER coloring text would misalign the bars. This guards
    against that regression."""
    import io
    import re
    from vitalyze import colors

    colors.enable()
    try:
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            report.print_summary({"scores": {"seo": 80, "ssl": 100, "overall": 90}})
        finally:
            sys.stdout = old_stdout
    finally:
        colors.disable()

    stripped = re.sub(r"\033\[[0-9;]*m", "", buf.getvalue())
    lines = [l for l in stripped.split("\n") if "OVERALL" in l or "seo" in l or "ssl" in l]
    bar_positions = [l.index("[") for l in lines]
    assert len(set(bar_positions)) == 1, f"misaligned bars: {bar_positions}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
