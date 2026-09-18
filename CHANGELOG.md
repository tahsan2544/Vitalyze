# Changelog

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
