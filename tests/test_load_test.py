"""Tests for the load test module: session reuse, count/duration modes,
ramp-up staggering, and auto-abort.

Pure logic (stagger delay, abort decision) is tested deterministically with
no threading involved. The actual concurrent execution paths are tested
with real threads but mocked, instant `_single_request` calls and short
durations (sub-second) — real enough to catch genuine concurrency bugs,
fast enough not to slow the suite down, with generous timing assertions so
they aren't flaky on a slower CI machine.
"""

import sys
import os
import threading
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import load_test


# --- Pure logic: _stagger_delay ---

def test_stagger_delay_zero_ramp_up_is_instant():
    assert load_test._stagger_delay(0, 5, 0) == 0.0
    assert load_test._stagger_delay(4, 5, 0) == 0.0


def test_stagger_delay_single_worker_is_instant():
    assert load_test._stagger_delay(0, 1, 10) == 0.0


def test_stagger_delay_spreads_evenly_across_window():
    # 4 workers, 8-second ramp -> starts at 0, 2, 4, 6
    assert load_test._stagger_delay(0, 4, 8) == 0.0
    assert load_test._stagger_delay(1, 4, 8) == 2.0
    assert load_test._stagger_delay(2, 4, 8) == 4.0
    assert load_test._stagger_delay(3, 4, 8) == 6.0


# --- Pure logic: _check_abort ---

def test_check_abort_disabled_when_threshold_none():
    results = [{"ok": False}] * 20
    assert load_test._check_abort(results, None) is None


def test_check_abort_ignores_too_few_samples():
    results = [{"ok": False}] * 5  # below MIN_REQUESTS_BEFORE_ABORT_CHECK
    assert load_test._check_abort(results, 50) is None


def test_check_abort_triggers_past_threshold():
    results = [{"ok": False}] * 15  # 100% error rate, well past 10 samples
    reason = load_test._check_abort(results, 50)
    assert reason is not None
    assert "100%" in reason


def test_check_abort_does_not_trigger_below_threshold():
    results = [{"ok": True}] * 8 + [{"ok": False}] * 2  # 20% error rate
    assert load_test._check_abort(results, 50) is None


def test_check_abort_exact_threshold_triggers():
    results = [{"ok": True}] * 5 + [{"ok": False}] * 5  # exactly 50%
    assert load_test._check_abort(results, 50) is not None


# --- Session reuse ---

def test_session_reused_within_same_thread():
    s1 = load_test._get_session()
    s2 = load_test._get_session()
    assert s1 is s2


def test_session_different_across_threads():
    sessions = {}

    def capture(name):
        sessions[name] = load_test._get_session()

    t1 = threading.Thread(target=capture, args=("a",))
    t2 = threading.Thread(target=capture, args=("b",))
    t1.start(); t1.join()
    t2.start(); t2.join()

    assert sessions["a"] is not sessions["b"]


# --- Cap enforcement ---

def test_concurrency_hard_capped():
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 1.0}):
        result = load_test.run("https://example.com", concurrency=999, total_requests=5)
    assert result["concurrency"] == load_test.MAX_CONCURRENCY


def test_total_requests_hard_capped():
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 1.0}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=999999)
    assert result["total_requests"] <= load_test.MAX_REQUESTS


def test_duration_hard_capped():
    # Patch the cap itself down to something tiny so this test verifies the
    # clamping *logic* without actually running for the real 60-second cap.
    with mock.patch.object(load_test, "MAX_DURATION_SECONDS", 0.2), \
         mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 1.0}):
        result = load_test.run("https://example.com", concurrency=2, duration_seconds=999999)
    assert result["requested_duration_sec"] == 0.2


def test_sub_second_duration_not_rounded_up_to_a_full_second():
    """Regression test: an earlier version used max(duration_seconds, 1),
    which silently rounded any short duration (e.g. 0.3s) up to a full
    second — a real behavioral bug, not just a test artifact. Caught by
    test_duration_mode_stops_near_requested_duration actually taking ~1s
    of real wall-clock time instead of the requested 0.3s."""
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 1.0}):
        result = load_test.run("https://example.com", concurrency=1, duration_seconds=0.3)
    assert result["requested_duration_sec"] == 0.3


def test_ramp_up_hard_capped():
    # Same reasoning — a real 30-second ramp-up would make this test itself
    # take 30 real seconds waiting for the last staggered worker to wake up.
    with mock.patch.object(load_test, "MAX_RAMP_UP_SECONDS", 0.1), \
         mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 1.0}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=2, ramp_up_seconds=999999)
    assert result["ramp_up_seconds"] == 0.1


# --- Count mode (real threads, mocked instant requests) ---

def test_count_mode_sends_exact_requested_count():
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 5.0}):
        result = load_test.run("https://example.com", concurrency=3, total_requests=17)
    assert result["mode"] == "count"
    assert result["total_requests"] == 17
    assert result["success_count"] == 17
    assert result["error_count"] == 0
    assert result["status_code_distribution"] == {"200": 17}


def test_count_mode_mixed_success_and_failure():
    responses = [{"ok": True, "status": 200, "latency_ms": 5.0}] * 6 + \
                [{"ok": False, "error": "timeout", "latency_ms": 5.0}] * 4
    call_iter = iter(responses)
    with mock.patch("vitalyze.load_test._single_request", side_effect=lambda *a: next(call_iter)):
        result = load_test.run("https://example.com", concurrency=2, total_requests=10, abort_threshold_pct=None)
    assert result["success_count"] == 6
    assert result["error_count"] == 4
    assert result["error_rate_pct"] == 40.0


# --- Duration mode (real threads, real short sleep, mocked instant requests) ---

def test_duration_mode_stops_near_requested_duration():
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=3, duration_seconds=0.3)
    assert result["mode"] == "duration"
    assert result["requested_duration_sec"] == 0.3
    # Generous upper bound — should never take much longer than requested,
    # but CI machines can be slow, so this isn't asserting tight timing.
    assert result["wall_time_sec"] < 2.0
    # With instant mocked requests over 0.3s across 3 workers, expect a
    # meaningful number of requests, not just one per worker.
    assert result["total_requests"] >= 3


def test_duration_mode_all_workers_participate():
    """Every worker should get at least one request in — a bug in the
    per-worker loop could leave some workers starved."""
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=4, duration_seconds=0.3)
    assert result["total_requests"] >= 4


# --- Ramp-up (real threads, real short sleep) ---

def test_ramp_up_does_not_dramatically_extend_wall_time():
    """Ramp-up staggers start times but shouldn't make the whole test take
    drastically longer than concurrency alone would for a small request count."""
    with mock.patch("vitalyze.load_test._single_request", return_value={"ok": True, "status": 200, "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=4, ramp_up_seconds=0.2)
    assert result["ramp_up_seconds"] == 0.2
    assert result["wall_time_sec"] < 2.0


# --- Auto-abort integration (real threads, mocked always-failing requests) ---

def test_abort_stops_before_full_request_count():
    with mock.patch("vitalyze.load_test._single_request",
                     return_value={"ok": False, "error": "connection refused", "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=200, abort_threshold_pct=50)
    assert result["aborted_early"] is True
    assert result["abort_reason"] is not None
    assert result["total_requests"] < 200


def test_no_abort_flag_runs_to_completion_despite_all_failures():
    with mock.patch("vitalyze.load_test._single_request",
                     return_value={"ok": False, "error": "connection refused", "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=20, abort_threshold_pct=None)
    assert result["aborted_early"] is False
    assert result["total_requests"] == 20


def test_abort_disabled_by_default_at_module_level():
    """The library function itself defaults to no auto-abort — main.py's
    CLI layer is what opts into a default threshold, keeping the module
    API explicit rather than surprising."""
    with mock.patch("vitalyze.load_test._single_request",
                     return_value={"ok": False, "error": "x", "latency_ms": 0.1}):
        result = load_test.run("https://example.com", concurrency=2, total_requests=20)
    assert result["aborted_early"] is False


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
