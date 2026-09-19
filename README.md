# 🩺 Vitalyze

**A command-line website performance & health analyzer.**
Point it at a URL and get a full checkup — DNS, redirects, response time (broken down phase-by-phase), SSL/TLS, security headers, caching, and SEO — scored and reported in seconds.

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Version](https://img.shields.io/badge/version-2.0.0-orange)

```
========================================
   V I T A L Y Z E
   Website Performance & Health Analyzer
========================================
```

---

## ⚠️ Before you touch `--load-test`

Vitalyze can send capped, concurrent traffic at a URL to see how it holds up. That feature is:

- ✅ For checking **your own site's** infrastructure
- ❌ **Not** for testing sites you don't own or don't have written permission to test

Read [`ETHICAL_USE.md`](ETHICAL_USE.md) before using `--load-test`. The caps aren't suggestions — they're hard limits in the code.

---

## 🆕 What's new in v2.0

| Upgrade | Why it matters |
|---|---|
| 🔬 **Phase-level timing** | Response time is no longer one lump number — it's broken into DNS lookup, TCP connect, TLS handshake, TTFB, and download, each measured separately via a raw socket-level client (not just `requests`) |
| 📈 **Real statistics** | Every timed metric now reports p90/p95/p99 and standard deviation, not just min/avg/max — so you can see *consistency*, not just averages |
| 🔀 **Redirect chain tracking** | Follows redirects hop-by-hop with per-hop timing, detects loops, and flags whether HTTP is upgraded to HTTPS — and every other check now analyzes the *final* destination, not an intermediate redirect |
| 🍪 **Cookie security analysis** | Flags cookies missing `Secure`, `HttpOnly`, or `SameSite` |
| 📦 **Caching analysis** | Reports `Cache-Control`, `ETag`, `Last-Modified`, `Vary`, and whether a response is actually cacheable |
| 🅰️ **Letter grades** | Every score now also shows as A–F at a glance |

---

## 📊 What it checks

| Category | 🔍 What it measures |
|---|---|
| 🌐 **DNS** | Resolution time, resolved IP addresses |
| 🔀 **Redirects** | Hop-by-hop chain, per-hop timing, loop detection, HTTP→HTTPS upgrade |
| ⚡ **Response Time** | DNS / TCP connect / TLS handshake / TTFB / download — each with full percentile stats |
| 🔒 **SSL/TLS** | Certificate issuer, protocol & cipher, days until expiry |
| 🛡️ **Security Headers** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, plus cookie flag hygiene |
| 📦 **Caching** | Cache-Control directives, ETag, Last-Modified, Vary, cacheability |
| 🔎 **SEO Basics** | Title/meta length, H1 count, viewport meta, canonical tag, robots.txt, sitemap.xml |
| 🚦 **Load Test** *(opt-in)* | Requests/sec, error rate, latency percentiles + stdev under capped concurrency |

Every category gets a **0–100 score** and a **letter grade**, rolled up into one overall grade.

---

## 📦 Installation

```bash
git clone https://github.com/yourusername/vitalyze.git
cd vitalyze
pip install -r requirements.txt
```

> Requires **Python 3.8+**. No dependencies beyond `requests` — the phase-timing engine is built on the standard library (`http.client`, `socket`, `ssl`).

---

## 🚀 Usage

**Basic scan:**
```bash
python main.py https://example.com
```

**Skip categories you don't need:**
```bash
python main.py https://example.com --skip seo ssl
```

**More samples for a stabler average:**
```bash
python main.py https://example.com --runs 10
```

**Export a report:**
```bash
python main.py https://example.com --output json --save report.json
python main.py https://example.com --output html --save report.html
```

**Load test (own site only, explicit opt-in required):**
```bash
python main.py https://yoursite.com --load-test --confirm-authorized \
    --concurrency 10 --requests 100
```

**Save your settings so you don't retype them:**
```bash
python main.py https://yoursite.com --runs 10 --skip seo --save-config vitalyze.config.json
```

**Reuse them next time — URL and flags all come from the file:**
```bash
python main.py --config vitalyze.config.json
```

A CLI flag always overrides the matching config value, so `python main.py --config vitalyze.config.json --runs 3` uses everything from the file except `runs`, which becomes `3` for that run. If a file named `vitalyze.config.json` exists in the current directory, it's picked up automatically — no `--config` needed.

Note: `--save-config` records every effective setting for that run (including defaults like `--output console`), not just the flags you typed — so the file is a complete, unambiguous snapshot rather than a diff.

**Track scores over time and compare against your last run:**
```bash
python main.py https://yoursite.com --trend
```

**Browse past runs without scanning again:**
```bash
python main.py https://yoursite.com --show-history        # last 10 runs
python main.py https://yoursite.com --show-history 30      # last 30 runs
```

Every run is recorded to a local SQLite file (`vitalyze_history.db` by default — safe to `.gitignore`, back up, or delete any time). Turn it off per-run with `--no-history`, or point it at a different file with `--history-db path/to/file.db`.

**Check the version:**
```bash
python main.py --version
```

---

## 🎛️ CLI options

| Flag | Default | Description |
|---|---|---|
| `url` | — | Target URL (required), e.g. `https://example.com` |
| `--runs` | `5` | Requests to average for response-time stats |
| `--skip` | none | Skip categories: `dns` `redirects` `response` `ssl` `headers` `caching` `seo` |
| `--load-test` | off | Run a capped, rate-limited load test |
| `--confirm-authorized` | off | Required with `--load-test` — confirms you're authorized |
| `--concurrency` | `5` | Load test workers (🔒 hard-capped at **20**) |
| `--requests` | `50` | Load test total requests (🔒 hard-capped at **500**) |
| `--output` | `console` | `console`, `json`, or `html` |
| `--save` | none | File path to save the JSON/HTML report |
| `--config` | none | Load settings from a JSON config file (auto-detects `./vitalyze.config.json`) |
| `--save-config` | none | Save this run's resolved settings to a JSON config file |
| `--history-db` | `vitalyze_history.db` | SQLite file where run history is stored |
| `--no-history` | off | Don't record this run's scores to history |
| `--trend` | off | Compare this run against the most recent previous run for this target |
| `--show-history [N]` | none | Show the last N runs (default 10) for this target and exit — no scan performed |
| `--version` | — | Print the installed version and exit |

---

## 🖥️ Example output

```
[1] DNS Resolution
    Host:          example.com
    Addresses:     93.184.216.34
    Resolve time:  12.4 ms

[2] Redirect Chain
    No redirects — direct 2xx/4xx/5xx response.

[3] Response Time
    Runs completed:   5 (failed: 0)
    HTTP version:     HTTP/1.1
    Compression:      gzip

    Phase breakdown (ms):
      DNS lookup           avg=2.1     median=2.0     p95=3.1     stdev=0.6
      TCP connect          avg=15.3    median=14.8    p95=18.2    stdev=2.1
      TLS handshake        avg=42.7    median=41.9    p95=48.0    stdev=3.4
      Time to first byte   avg=98.2    median=95.5    p95=112.0   stdev=8.9
      Download             avg=12.4    median=12.0    p95=15.1    stdev=1.8

    Total time (ms):  avg=168.4 median=165.0 p90=180.2 p95=185.6 p99=190.1 stdev=12.3

...

============================================================
SUMMARY
============================================================
  response_time      [##################--] 91/100  [A]
  ssl                [####################] 100/100  [A]
  security_headers   [###########---------] 55/100  [D]
  caching            [################----] 80/100  [B]
  seo                [################----] 80/100  [B]
  redirects          [####################] 100/100  [A]
------------------------------------------------------------
  OVERALL             [################----] 84/100  [B]
============================================================
```

---

## 🗂️ Project structure

| Path | Purpose |
|---|---|
| `main.py` | CLI entry point |
| `vitalyze/dns_check.py` | DNS resolution timing |
| `vitalyze/redirects.py` | Redirect chain tracking + loop detection |
| `vitalyze/timing.py` | Low-level phase-by-phase HTTP timing (DNS/TCP/TLS/TTFB/download) |
| `vitalyze/response_time.py` | Runs `timing.py` over N samples, computes full statistics |
| `vitalyze/stats_utils.py` | Shared percentile/stdev helper used by response time & load test |
| `vitalyze/ssl_check.py` | Certificate inspection |
| `vitalyze/security_headers.py` | Security header audit + cookie flag analysis |
| `vitalyze/caching.py` | Cache-Control/ETag/Last-Modified analysis |
| `vitalyze/config.py` | JSON config file load/save (`--config`/`--save-config`) |
| `vitalyze/history.py` | SQLite-backed run history, trend comparison (`--trend`/`--show-history`) |
| `vitalyze/seo_basics.py` | On-page SEO checks |
| `vitalyze/load_test.py` | 🔒 Capped, single-target load test |
| `vitalyze/report.py` | Scoring, letter grades, JSON/HTML export |
| `tests/` | Unit tests (64 tests, all mocked — no real network needed) |
| `.github/workflows/ci.yml` | Auto-runs tests on push/PR |
| `ETHICAL_USE.md` | Responsible-use policy — read before load testing |

---

## 🧪 Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

All 64 tests run against mocked sockets/HTTP responses — no live network calls, so they pass in CI or offline exactly the same way.

---

## 🛣️ Roadmap

| Idea | Status |
|---|---|
| Slack/webhook alerts on score regressions | 🔜 next up |
| Multi-page crawl (same host only, capped) | 💭 planned |
| Core Web Vitals — heuristic estimate, not real LCP/CLS (needs a browser for that) | 💭 planned |
| Screenshot capture — desktop only, won't run in Termux | 💭 planned |
| IPv6-aware DNS/connect reporting | 💭 planned |

---

## 🤝 Contributing

Issues and PRs welcome! One rule: PRs that remove the load-test safety caps or add multi-target/subdomain scanning will be declined — see [`ETHICAL_USE.md`](ETHICAL_USE.md) for why.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
