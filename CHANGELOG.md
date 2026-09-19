# Changelog

## v2.3.0

**Visual polish** — the console output now looks like a finished tool
instead of a debug log: colors, icons, and a plain-language verdict, not
just numbers.

### Added
- `vitalyze/colors.py` — ANSI color helpers. On by default in a real
  terminal, auto-off when piping to a file or when `NO_COLOR` is set
  (https://no-color.org/), and always off in JSON/HTML output (which never
  touch this module at all — the raw results dict stays plain data).
- `--no-color` flag to force colors off regardless of terminal detection.
- ✓ / ✗ / ⚠ icons replacing the old `[OK]` / `[--]` / `[x]` / `[!]` text
  tags across every check module: DNS, redirects, SSL, security headers,
  caching, SEO, load test, and history trend arrows.
- Colored score bars, numbers, and letter grades in the console summary.
- A plain-language verdict line under the score summary — "Excellent",
  "Good", "Fair", "Needs work", or "Poor" — instead of leaving the
  numbers to speak for themselves.
- Colored grade badges in the HTML report (was one flat static gradient
  before) plus the same verdict line.
- 6 new unit tests for the color module (enabled/disabled state, score
  thresholds, icon presence) plus 2 new tests in `test_report.py`
  (verdict thresholds, and a regression guard for the alignment bug
  described below).

### Fixed
- **Column alignment bug**: coloring a label *before* padding it (e.g.
  `f"{colors.bold(text):<18}"`) throws off visual alignment, because
  Python's `:<N` padding counts the invisible ANSI escape bytes toward the
  string's length. Every colored/padded line was restructured to pad the
  plain text first, then wrap the already-padded result in color.
- **Python 3.8–3.11 compatibility**: caught and fixed two places using a
  nested f-string with an escaped quote inside the outer f-string's
  expression (e.g. `f"...{fn(f'...\\"...\\"...')}"`). This is valid only
  on Python 3.12+ (PEP 701) — on 3.8–3.11 it's a hard `SyntaxError`. This
  sandbox runs 3.12, so `py_compile` didn't catch it; found by manually
  grepping for the pattern across the codebase, since the README commits
  to 3.8+ support and Termux/older systems could hit it.

## v2.2.0

**History tracking** — second upgrade in the planned batch (webhook alerts,
multi-page crawl, Core Web Vitals estimate, screenshot capture still to
come — see README roadmap).

### Added
- `vitalyze/history.py` — records every scan's scores to a local SQLite
  file (`vitalyze_history.db` by default, zero new dependencies since
  sqlite3 is in the standard library).
- `--trend` — compares this run's scores against the most recent previous
  run for the same target, printing a per-category delta.
- `--show-history [N]` — lists the last N runs (default 10) for a target
  and exits without running a new scan.
- `--history-db FILE` / `--no-history` — choose where history is stored,
  or opt out of recording for a given run.
- 10 new unit tests using real temporary SQLite files (not mocks — sqlite3
  against a temp file is fast and doesn't touch the network) plus 6 new
  end-to-end integration tests covering: first-ever scan, trend delta
  against a real prior run, show-history in both console and JSON mode,
  `--no-history` correctly skipping a write, and trend against a
  never-before-seen target.

### Notes
- History is scoped per exact target URL string (what you typed, not the
  post-redirect destination) — matches how you'd naturally think of "my
  site's history."
- `vitalyze_history.db` and any `*.db` file are now in `.gitignore` — this
  is local run data, not something to commit.

## v2.1.0

**Config file support** — the first of a planned batch of upgrades (history
tracking, webhook alerts, multi-page crawl, Core Web Vitals estimate,
screenshot capture — see README roadmap).

### Added
- `vitalyze/config.py` — load/save run settings as JSON. `--save-config
  FILE` writes the current run's resolved settings; `--config FILE` (or an
  auto-detected `./vitalyze.config.json`) loads them back. CLI flags always
  override the matching config value.
- 8 new unit tests for config load/save, including invalid-JSON,
  non-object, and unknown-key rejection.
- 5 end-to-end integration tests covering the full CLI flow: save → load,
  CLI-overrides-config precedence, config-only URL, missing-URL error, and
  unknown-key error — run against real temp files, not just mocks.

### Changed
- `url` is now an optional positional argument (can come from `--config`
  instead); a clear error is printed if neither the CLI nor a config file
  supplies one.
- `--skip` and `--output` values are now validated manually after config
  merging, since argparse's `choices` validation doesn't apply to values
  set via `set_defaults()` (i.e. values coming from a config file).

## v2.0.0

**Precision upgrade** — response time is now measured phase-by-phase instead
of as one lump number, and every statistic reports spread, not just an average.

### Added
- `vitalyze/timing.py` — new socket-level HTTP client that times DNS lookup,
  TCP connect, TLS handshake, TTFB, and download as separate phases, built
  on `http.client`/`socket`/`ssl` (no new dependencies).
- `vitalyze/stats_utils.py` — shared percentile (p90/p95/p99) and standard
  deviation helper, now used by both response time and the load test.
- `vitalyze/redirects.py` — follows redirect chains hop-by-hop, times each
  hop, detects redirect loops, and flags HTTP→HTTPS upgrades.
- `vitalyze/caching.py` — reports Cache-Control directives, ETag,
  Last-Modified, Vary, and whether a response is actually cacheable.
- Cookie security analysis in `security_headers.py` — flags cookies missing
  `Secure`, `HttpOnly`, or `SameSite`.
- Letter grades (A–F) alongside every numeric score.
- `--version` flag.
- 46 unit tests across 6 test files, all running against mocked sockets/HTTP
  responses (no live network required).

### Changed
- **Every check now analyzes the final destination URL**, not an
  intermediate redirect. Vitalyze resolves the redirect chain first, then
  runs response time, SSL, headers, caching, and SEO checks against the
  resolved URL — so a `http://` → `https://` redirect no longer gets
  measured as if the 301 response itself were the page.
- `response_time.py` rewritten to use the new phase-timing engine instead
  of a single `requests.get()` call.
- `load_test.py` latency stats now report p50/p90/p95/p99 and stdev
  instead of just min/avg/p95/max.
- `report.py` scoring extended to cover the two new categories (`caching`,
  `redirects`) and fixed an edge case where a load test with 100% failed
  requests could crash the scorer (`None["avg"]`).

### Fixed
- `timing.single_request()` now wraps connection *construction* in the
  try/except, not just `connect()` — a constructor-time failure no longer
  propagates uncaught.

## v1.0.0

Initial release: DNS resolution, response time (single total-time
measurement), SSL/TLS certificate check, security header presence check,
SEO basics, and a capped/rate-limited load test.
