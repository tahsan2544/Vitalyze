# Changelog

## v2.5.0

**Accuracy pass** — the three fixes identified while reviewing v2.4, all
finished and tested, per explicit "accuracy over features" direction.

### Fixed
- **SEO checks now use a real HTML parser** (`html.parser.HTMLParser`,
  standard library) instead of regex. The old regex silently returned
  `None` for a meta description when attributes were in reversed order
  (`content` before `name`) or unquoted — both valid, common HTML that a
  regex anchored on a specific attribute order/quoting gets wrong. Proven
  with a before/after test showing the exact failure.
- **Security headers now score content quality, not just presence.** A
  wide-open `Content-Security-Policy: default-src *` used to score
  identically to a properly scoped one. `_assess_header_quality()` now
  checks for known-bad patterns per header (wildcard CSP sources,
  unsafe-inline/unsafe-eval, a too-short HSTS max-age, a wrong
  X-Content-Type-Options value, deprecated X-Frame-Options values,
  unsafe-url Referrer-Policy) and reduces that header's contribution to
  the score accordingly, with the reason shown in console output.
- **Response time now also measures connection reuse.** Every phase
  measurement forces `Connection: close`, paying a full DNS+TCP+TLS
  handshake per request — a real "worst case first visit" number, but not
  what a browser experiences reusing a connection. A new "warm" section
  (`timing.run_session()`) measures N requests over ONE kept-alive
  connection and reports both numbers side by side, with a plain-language
  note on the speedup.

### Added
- `scripts/bump_version.py` + `githooks/pre-commit` — a version
  auto-bump tool. One-time setup: `git config core.hooksPath githooks`.
  After that, every commit bumps the patch version automatically and
  stages it into that same commit. Pure Python, no shell-specific syntax,
  tested end-to-end in a real git repo (not just mocked) across two
  consecutive commits.
- 45 new tests across `test_seo_basics.py` (13), the security-headers
  quality logic (15 new cases in `test_security_headers.py`),
  `test_response_time.py` (5, new file), `run_session` coverage in
  `test_timing.py` (5 new cases), and `test_bump_version.py` (7, new file).
  130 tests total, all still mocked/temp-file based — no live network
  required anywhere in the suite.

### Changed
- README rewritten with per-platform command blocks (Linux/macOS,
  Windows, Termux) instead of one generic set of commands, author credit,
  and the version-automator setup documented.

## v2.4.0

**Webhook/Slack alerts** — the last of the originally requested feature
batch. From here, the roadmap shifts to accuracy improvements over new
features, per explicit direction.

### Added
- `vitalyze/alerts.py` — sends a notification to a webhook URL when the
  score regresses. `--webhook-format slack` (default) sends Slack's
  `{text: ...}` shape; `--webhook-format generic` sends raw
  `{target, scores, trend}` JSON for a custom integration.
- `--alert-threshold N` (default 10) — minimum point drop, in the overall
  score or any single category, that triggers a send. `--alert-always`
  overrides this to send every run regardless.
- A security warning printed when `--save-config` and `--webhook` are used
  together: a webhook URL is effectively a credential, and saving it to a
  config file that later gets committed to a public repo would leak it.
- 13 new unit tests (should-alert threshold logic, Slack text formatting,
  generic payload shape, HTTP/connection error handling — all mocked, no
  real network) plus 5 end-to-end integration tests: no alert on a
  first-ever run (nothing to compare against), a real regression
  triggering and sending, a sub-threshold drop correctly not triggering,
  `--alert-always` forcing a send, and the webhook outcome appearing in
  JSON output.

### Changed
- Trend is now computed internally whenever `--webhook` is set, even
  without `--trend` — you don't need both flags for the alert logic to
  work, only to also see the trend printed to console.
- Roadmap re-prioritized around accuracy improvements (real HTML parsing,
  header content-quality scoring, connection-reuse-aware timing) ahead of
  the previously planned Core Web Vitals heuristic and screenshot capture,
  per explicit "accuracy over features" direction.

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
