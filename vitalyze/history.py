"""Stores each scan's scores in a local SQLite database, keyed by the
target URL, so scores can be compared across runs over time.

Uses the standard library's sqlite3 — no new dependency, and the resulting
.db file is a single portable file (easy to .gitignore, back up, or delete).
"""

import json
import os
import sqlite3
import time

from . import colors

DEFAULT_HISTORY_DB_FILENAME = "vitalyze_history.db"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            host TEXT,
            timestamp REAL NOT NULL,
            scores_json TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_target_ts ON runs(target, timestamp)")
    conn.commit()
    return conn


def record(db_path: str, target: str, host: str, timestamp: float, scores: dict) -> None:
    """Insert one run's scores. Never overwrites — history is append-only."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO runs (target, host, timestamp, scores_json) VALUES (?, ?, ?, ?)",
            (target, host, timestamp, json.dumps(scores)),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_history(db_path: str, target: str, limit: int = 10) -> list:
    """Most recent `limit` runs for `target`, newest first. [] if no db or no rows.

    Deliberately avoids creating the db file for a pure read on a target
    that's never been scanned — sqlite3.connect() creates the file as a
    side effect, so this checks existence first.
    """
    if not os.path.isfile(db_path):
        return []

    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT timestamp, scores_json FROM runs WHERE target = ? ORDER BY timestamp DESC LIMIT ?",
            (target, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [{"timestamp": ts, "scores": json.loads(scores_json)} for ts, scores_json in rows]


def previous_run(db_path: str, target: str) -> dict:
    """The single most recent run for `target`, or None if there isn't one."""
    records = fetch_history(db_path, target, limit=1)
    return records[0] if records else None


def compute_deltas(previous_scores: dict, current_scores: dict) -> dict:
    """Per-category score change (current - previous). Only for categories
    present in both runs — a category skipped in either run is left out
    rather than reported as a misleading +100/-100 swing."""
    deltas = {}
    for category in set(previous_scores) & set(current_scores):
        deltas[category] = current_scores[category] - previous_scores[category]
    return deltas


def _arrow(delta: int) -> str:
    if delta > 0:
        return colors.green(f"{colors.UP} +{delta}")
    if delta < 0:
        return colors.red(f"{colors.DOWN} {delta}")
    return colors.dim(f"{colors.FLAT} +0")


def print_trend(trend: dict, previous_timestamp: float) -> None:
    if trend is None:
        print("    No previous run found for this target yet — nothing to compare.")
        return

    ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(previous_timestamp))
    print(f"    Compared to previous run ({ts_str}):")
    for category, delta in sorted(trend.items()):
        if category == "overall":
            continue
        print(f"      {category:<18} {_arrow(delta)}")
    if "overall" in trend:
        overall_label = colors.bold(f"{'OVERALL':<18}")
        print(f"      {overall_label} {_arrow(trend['overall'])}")


def print_history_table(records: list, target: str) -> None:
    from . import report  # local import: report.py doesn't import history.py, no cycle

    if not records:
        print(f"    No history found for {target}.")
        print("    Run a scan against this URL first (history recording is on by default).")
        return

    print(f"    History for {target} (most recent first):")
    for rec in records:
        ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(rec["timestamp"]))
        overall = rec["scores"].get("overall")
        letter = report.grade(overall) if overall is not None else "N/A"
        others = ", ".join(f"{k}={v}" for k, v in rec["scores"].items() if k != "overall")
        overall_colored = colors.score_color(overall) if overall is not None else "N/A"
        letter_colored = colors.color_for_score(overall)(letter) if overall is not None else letter
        print(f"      {ts_str}   overall={overall_colored} [{letter_colored}]   ({others})")
