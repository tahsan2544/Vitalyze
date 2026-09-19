"""Tests for run history storage and trend comparison.

Uses real temporary SQLite files rather than mocks — sqlite3 with a temp
file is fast and doesn't touch the network, so there's no reason to fake it.
"""

import sys
import os
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import history


def test_fetch_history_missing_db_returns_empty_without_creating_file():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "nope.db")
        result = history.fetch_history(db_path, "https://example.com")
        assert result == []
        assert not os.path.isfile(db_path), "a pure read should not create the db file"


def test_record_then_fetch_round_trip():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        history.record(db_path, "https://example.com", "example.com", 1000.0, {"overall": 80, "seo": 90})
        records = history.fetch_history(db_path, "https://example.com")
        assert len(records) == 1
        assert records[0]["scores"] == {"overall": 80, "seo": 90}
        assert records[0]["timestamp"] == 1000.0


def test_fetch_history_newest_first():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        history.record(db_path, "https://example.com", "example.com", 1000.0, {"overall": 50})
        history.record(db_path, "https://example.com", "example.com", 2000.0, {"overall": 70})
        history.record(db_path, "https://example.com", "example.com", 1500.0, {"overall": 60})
        records = history.fetch_history(db_path, "https://example.com")
        timestamps = [r["timestamp"] for r in records]
        assert timestamps == [2000.0, 1500.0, 1000.0]


def test_fetch_history_respects_limit():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        for i in range(5):
            history.record(db_path, "https://example.com", "example.com", float(i), {"overall": i})
        records = history.fetch_history(db_path, "https://example.com", limit=2)
        assert len(records) == 2


def test_history_is_scoped_per_target():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        history.record(db_path, "https://a.com", "a.com", 1000.0, {"overall": 10})
        history.record(db_path, "https://b.com", "b.com", 1000.0, {"overall": 90})
        a_records = history.fetch_history(db_path, "https://a.com")
        b_records = history.fetch_history(db_path, "https://b.com")
        assert len(a_records) == 1 and a_records[0]["scores"]["overall"] == 10
        assert len(b_records) == 1 and b_records[0]["scores"]["overall"] == 90


def test_previous_run_returns_none_when_empty():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        assert history.previous_run(db_path, "https://example.com") is None


def test_previous_run_returns_most_recent():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        history.record(db_path, "https://example.com", "example.com", 1000.0, {"overall": 50})
        history.record(db_path, "https://example.com", "example.com", 2000.0, {"overall": 70})
        prev = history.previous_run(db_path, "https://example.com")
        assert prev["timestamp"] == 2000.0
        assert prev["scores"]["overall"] == 70


def test_compute_deltas_basic():
    deltas = history.compute_deltas({"overall": 70, "seo": 80}, {"overall": 85, "seo": 80})
    assert deltas["overall"] == 15
    assert deltas["seo"] == 0


def test_compute_deltas_ignores_categories_not_in_both():
    deltas = history.compute_deltas({"overall": 70, "seo": 80}, {"overall": 85, "ssl": 100})
    assert "seo" not in deltas
    assert "ssl" not in deltas
    assert deltas["overall"] == 15


def test_record_append_only_does_not_overwrite():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "h.db")
        history.record(db_path, "https://example.com", "example.com", 1000.0, {"overall": 50})
        history.record(db_path, "https://example.com", "example.com", 2000.0, {"overall": 70})
        records = history.fetch_history(db_path, "https://example.com", limit=10)
        assert len(records) == 2


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
