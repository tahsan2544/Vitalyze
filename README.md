# 🩺 Vitalyze

**A command-line website performance & health analyzer.**
Point it at a URL and get a full checkup — DNS, redirects, response time (broken down phase-by-phase, cold *and* connection-reused), SSL/TLS, security headers (content-quality scored, not just presence), caching, and SEO — scored and reported in seconds.

Made by **Tahsan Ahmed**.

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Version](https://img.shields.io/badge/version-2.7.0-orange)

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

## 🎯 Accuracy, not just features (v2.5)

Three real correctness gaps got fixed, not just new checkboxes added:

| Fix | What was wrong before |
|---|---|
| 🧩 **Real HTML parser for SEO checks** | The old regex-based extraction silently missed a valid meta description if attributes were reversed (`content` before `name`) or unquoted — both totally normal HTML. Now uses `html.parser.HTMLParser` (standard library), which handles real-world HTML correctly. |
| 🛡️ **Header content quality, not just presence** | A wide-open `Content-Security-Policy: default-src *` used to score identically to a strict, well-scoped one. Now each present header's *value* is checked for known-bad patterns (wildcard CSP sources, `unsafe-inline`, a too-short HSTS `max-age`, a wrong `X-Content-Type-Options` value, and more) and scored accordingly. |
| 🔌 **Connection-reuse timing** | Every response-time measurement forced a fresh TCP+TLS handshake per request — a real "worst case first visit" number, but not what a browser experiences reusing a connection. A new "warm" measurement now reports both side by side. |

---

## 🆕 Full feature list

| Feature | Why it matters |
|---|---|
| 🔬 **Phase-level timing** | DNS lookup, TCP connect, TLS handshake, TTFB, and download measured separately via a raw socket-level client, not just one lump `requests` call |
| 🔌 **Cold vs. warm timing** | Fresh-connection ("cold") and connection-reused ("warm") numbers reported side by side |
| 📈 **Real statistics** | p90/p95/p99 and standard deviation on every timed metric, not just min/avg/max |
| 🔀 **Redirect chain tracking** | Hop-by-hop timing, loop detection, HTTP→HTTPS upgrade detection — every other check analyzes the *final* destination |
| 🛡️ **Security headers, content-aware** | Presence *and* quality of HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, plus cookie flag hygiene |
| 📦 **Caching analysis** | `Cache-Control`, `ETag`, `Last-Modified`, `Vary`, and actual cacheability |
| 🅰️ **Letter grades** | Every score also shows as A–F at a glance |
| ⚙️ **Config files** | `--save-config` / `--config` — reuse a target and flags without retyping them |
| 📜 **History tracking** | Every run recorded locally; `--trend` compares to your last run, `--show-history` browses past runs |
| 🔔 **Webhook/Slack alerts** | `--webhook` notifies you, only on a real regression by default |
| 🎨 **Colored console output** | ✓/✗/⚠ icons, color-coded scores, a plain-language verdict line — auto-disables when piping to a file or via `--no-color` |
| 🔢 **Auto-versioning** | A git hook bumps the patch version on every commit automatically |
| 🔓 **Mixed content detection** | Flags HTTP resources on an HTTPS page — objective, not a guess |
| ♿ **Accessibility basics** | `<html lang>` attribute + image alt-text coverage, scored |
| 📢 **Social meta tags** | Open Graph / Twitter Card presence — informational, not scored (see reasoning in the module) |
| 🌐 **HTTP/2 detection** | Via ALPN during the TLS handshake — reports what actually got negotiated |

---

## 📊 What it checks

| Category | 🔍 What it measures |
|---|---|
| 🌐 **DNS** | Resolution time, resolved IP addresses |
| 🔀 **Redirects** | Hop-by-hop chain, per-hop timing, loop detection, HTTP→HTTPS upgrade |
| ⚡ **Response Time** | DNS / TCP connect / TLS handshake / TTFB / download, cold *and* warm (connection-reused), each with full percentile stats |
| 🔒 **SSL/TLS** | Certificate issuer, protocol & cipher, days until expiry, HTTP/2 support (via ALPN) |
| 🛡️ **Security Headers** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy — presence *and* content quality — plus cookie flag hygiene |
| 📦 **Caching** | Cache-Control directives, ETag, Last-Modified, Vary, cacheability |
| 🔎 **SEO Basics** | Title/meta length, H1 count, viewport meta, canonical tag, robots.txt, sitemap.xml — via a real HTML parser |
| 🔓 **Mixed Content** | HTTP resources (images, scripts, stylesheets, iframes, media) loaded on an HTTPS page — exactly what browsers warn or block on |
| 📢 **Social Meta Tags** | Open Graph and Twitter Card tags — how the page looks when shared on social media (informational, not scored) |
| ♿ **Accessibility** | `<html lang>` attribute, image alt-text coverage |
| 🚦 **Load Test** *(opt-in)* | Requests/sec, error rate, latency percentiles + stdev under capped concurrency |

Every category gets a **0–100 score** and a **letter grade**, rolled up into one overall grade.

---

## 📦 Installation

Pick your platform:

### 🐧 Linux / macOS

```bash
git clone https://github.com/tahsan2544/Vitalyze.git
cd Vitalyze
pip install -r requirements.txt
python3 main.py https://example.com
```

### 🪟 Windows (PowerShell or CMD)

```powershell
git clone https://github.com/tahsan2544/Vitalyze.git
cd Vitalyze
pip install -r requirements.txt
python main.py https://example.com
```
If `python` isn't recognized, try `py -3 main.py ...` instead.

### 📱 Termux (Android)

```bash
pkg install python git
git clone https://github.com/tahsan2544/Vitalyze.git
cd Vitalyze
pip install -r requirements.txt
python main.py https://example.com
```
If the SSL check fails with a certificate-verification error on a fresh Termux install, run `pkg install ca-certificates` — Termux sometimes ships without a trusted CA bundle for raw-socket TLS connections (the rest of Vitalyze uses `requests`, which bundles its own CAs and isn't affected).

> Requires **Python 3.8+** on any platform. No dependencies beyond `requests` — the phase-timing engine is built entirely on the standard library (`http.client`, `socket`, `ssl`, `sqlite3`, `html.parser`).

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

**Or run for a fixed duration instead of a fixed request count:**
```bash
python main.py https://yoursite.com --load-test --confirm-authorized \
    --concurrency 10 --duration 30
```

**Ease into full load gradually instead of an instant spike:**
```bash
python main.py https://yoursite.com --load-test --confirm-authorized \
    --concurrency 10 --duration 30 --ramp-up 10
```

The load test auto-stops if the error rate crosses 90% (`--abort-threshold` to change it, `--no-abort` to disable) — if your target is already struggling, sending more traffic doesn't tell you anything new. Each simulated worker also keeps a persistent, reused connection for its requests (not a fresh TCP+TLS handshake every time), so this measures realistic concurrent-user behavior rather than the cost of repeated cold connections.

**Save your settings so you don't retype them:**
```bash
python main.py https://yoursite.com --runs 10 --skip seo --save-config vitalyze.config.json
```

**Reuse them next time — URL and flags all come from the file:**
```bash
python main.py --config vitalyze.config.json
```

A CLI flag always overrides the matching config value, so `python main.py --config vitalyze.config.json --runs 3` uses everything from the file except `runs`, which becomes `3` for that run. If a file named `vitalyze.config.json` exists in the current directory, it's picked up automatically — no `--config` needed.

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

**Get a Slack notification when your score regresses:**
```bash
python main.py https://yoursite.com --webhook https://hooks.slack.com/services/xxx/yyy/zzz
```

Only sends when the overall score (or any single category) drops by 10+ points versus your last run (`--alert-threshold` to change that) — not every run. Use `--alert-always` to notify unconditionally, or `--webhook-format generic` to send raw JSON to a non-Slack endpoint instead of Slack's `{text: ...}` shape.

⚠️ **A webhook URL is effectively a password** — anyone who has it can post to your channel. If you `--save-config` alongside `--webhook`, don't commit that config file to a public repo (Vitalyze will warn you if you do this in one command).

**Check the version:**
```bash
python main.py --version
```

---

## 🔢 Auto-incrementing version on every commit

Vitalyze's own version bumps itself. One-time setup after cloning:

```bash
git config core.hooksPath githooks
```

From then on, every `git commit` runs [`githooks/pre-commit`](githooks/pre-commit), which bumps the patch number in `vitalyze/__init__.py` (e.g. `2.5.0` → `2.5.1`) and stages that change into the same commit — no separate "bump version" commit needed. Works identically on Linux, macOS, Windows (Git Bash), and Termux; it's pure Python underneath ([`scripts/bump_version.py`](scripts/bump_version.py)), so there's nothing shell-specific to break across platforms.

This bumps the **patch** number only, on *every* commit — including docs-only or test-only changes. That's a deliberate tradeoff for simplicity: it treats every commit as worth a patch release rather than requiring you to judge that each time. If you want more controlled versioning later (only bump on meaningful changes, or bump minor/major manually for bigger releases), just don't run the `git config` line above, or bump `vitalyze/__init__.py` by hand when you want to override the auto-bump.

---

## 🎛️ CLI options

| Flag | Default | Description |
|---|---|---|
| `url` | — | Target URL (required), e.g. `https://example.com` |
| `--runs` | `5` | Requests to average for response-time stats |
| `--skip` | none | Skip categories: `dns` `redirects` `response` `ssl` `headers` `caching` `seo` `mixed_content` `social` `accessibility` |
| `--load-test` | off | Run a capped, rate-limited load test |
| `--confirm-authorized` | off | Required with `--load-test` — confirms you're authorized |
| `--concurrency` | `5` | Load test workers (🔒 hard-capped at **20**) |
| `--requests` | `50` | Load test total requests (🔒 hard-capped at **500**) — ignored if `--duration` is given |
| `--duration` | none | Load test: run for N seconds instead of a fixed count (🔒 hard-capped at **60s**) |
| `--ramp-up` | `0` | Load test: seconds to gradually reach full concurrency (🔒 hard-capped at **30s**) |
| `--abort-threshold` | `90` | Load test: auto-stop if the error rate reaches this percent |
| `--no-abort` | off | Disable the load test's auto-abort-on-high-error-rate behavior |
| `--output` | `console` | `console`, `json`, or `html` |
| `--save` | none | File path to save the JSON/HTML report |
| `--config` | none | Load settings from a JSON config file (auto-detects `./vitalyze.config.json`) |
| `--save-config` | none | Save this run's resolved settings to a JSON config file |
| `--history-db` | `vitalyze_history.db` | SQLite file where run history is stored |
| `--no-history` | off | Don't record this run's scores to history |
| `--trend` | off | Compare this run against the most recent previous run for this target |
| `--show-history [N]` | none | Show the last N runs (default 10) for this target and exit — no scan performed |
| `--no-color` | off | Disable colored output (auto-disabled anyway when piping to a file, or via `NO_COLOR` env var) |
| `--webhook` | none | URL to notify (Slack-compatible by default) when the score regresses |
| `--webhook-format` | `slack` | `slack` for `{text: ...}`, or `generic` for raw `{target, scores, trend}` JSON |
| `--alert-threshold` | `10` | Minimum point drop (overall or any category) that triggers `--webhook` |
| `--alert-always` | off | Send the `--webhook` notification every run, not just on a regression |
| `--version` | — | Print the installed version and exit |

---

## 🖥️ Example output

*(In a real terminal, ✓/✗/⚠ and scores render in green/yellow/red — shown plain here since Markdown can't display ANSI colors.)*

```
[1] DNS Resolution
    ✓ Resolved
    Host:          example.com
    Addresses:     93.184.216.34
    Resolve time:  12.4 ms

[2] Redirect Chain
    ✓ No redirects — direct 2xx/4xx/5xx response.

[3] Response Time
    Runs completed:   5 (failed: 0)
    HTTP version:     HTTP/1.1
    Compression:      gzip

    Phase breakdown (ms) — fresh connection per request:
      DNS lookup           avg=2.1     median=2.0     p95=3.1     stdev=0.6
      TCP connect          avg=15.3    median=14.8    p95=18.2    stdev=2.1
      TLS handshake        avg=42.7    median=41.9    p95=48.0    stdev=3.4
      Time to first byte   avg=98.2    median=95.5    p95=112.0   stdev=8.9
      Download             avg=12.4    median=12.0    p95=15.1    stdev=1.8

    Total time (ms):  avg=168.4 median=165.0 p90=180.2 p95=185.6 p99=190.1 stdev=12.3

    Connection reuse (warm, HTTP keep-alive):
      First request (cold):   168.4 ms — full DNS+TCP+TLS setup
      Reused requests (warm): avg=28.9 median=27.5 p95=32.0 (n=4)
      note: 5.8x faster once the connection is already open — the numbers
      above reflect a fresh-connection worst case, not a typical repeat visit

...

[5] Security Headers
    Score:  70/100 (headers + cookie hygiene, penalty: -0)
      ✓ Strict-Transport-Security: max-age=31536000
      ⚠ Content-Security-Policy: default-src *
        -> wildcard default-src/script-src — provides little real protection

...

============================================================
SUMMARY
============================================================
  response_time      [##################--] 91/100  [A]
  ssl                [####################] 100/100  [A]
  security_headers   [###########---------] 70/100  [C]
  caching            [################----] 80/100  [B]
  seo                [################----] 80/100  [B]
  redirects          [####################] 100/100  [A]
------------------------------------------------------------
  OVERALL             [################----] 87/100  [B]
============================================================
  Good — solid overall, a few things worth polishing.
============================================================
```

---

## 🗂️ Project structure

| Path | Purpose |
|---|---|
| `main.py` | CLI entry point |
| `vitalyze/dns_check.py` | DNS resolution timing |
| `vitalyze/redirects.py` | Redirect chain tracking + loop detection |
| `vitalyze/timing.py` | Phase-by-phase HTTP timing (DNS/TCP/TLS/TTFB/download) + connection-reuse ("warm") sessions |
| `vitalyze/response_time.py` | Runs `timing.py` over N samples, computes cold + warm statistics |
| `vitalyze/stats_utils.py` | Shared percentile/stdev helper |
| `vitalyze/ssl_check.py` | Certificate inspection |
| `vitalyze/security_headers.py` | Security header presence + content-quality scoring, cookie flag analysis |
| `vitalyze/caching.py` | Cache-Control/ETag/Last-Modified analysis |
| `vitalyze/seo_basics.py` | On-page SEO checks via a real HTML parser |
| `vitalyze/mixed_content.py` | Detects HTTP resources loaded on an HTTPS page |
| `vitalyze/social_meta.py` | Open Graph / Twitter Card tag detection (informational) |
| `vitalyze/accessibility.py` | `<html lang>` attribute and image alt-text coverage |
| `vitalyze/config.py` | JSON config file load/save (`--config`/`--save-config`) |
| `vitalyze/history.py` | SQLite-backed run history, trend comparison (`--trend`/`--show-history`) |
| `vitalyze/colors.py` | ANSI color helpers for console output (auto-detects TTY, respects `NO_COLOR`) |
| `vitalyze/alerts.py` | Slack/webhook notifications on score regression (`--webhook`) |
| `vitalyze/load_test.py` | 🔒 Capped, single-target load test — session reuse, duration/count modes, ramp-up, auto-abort |
| `vitalyze/report.py` | Scoring, letter grades, JSON/HTML export |
| `scripts/bump_version.py` | Version auto-bump logic, called by the pre-commit hook |
| `githooks/pre-commit` | Git hook: bumps the version and stages it on every commit |
| `tests/` | Unit tests (189 tests, all mocked/temp-file based — no real network needed) |
| `.github/workflows/ci.yml` | Auto-runs tests on push/PR |
| `ETHICAL_USE.md` | Responsible-use policy — read before load testing |
| `CONTRIBUTING.md` | Test workflow and PR rules |
| `SECURITY.md` | Private vulnerability reporting and scope |

---

## 🧪 Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

All 189 tests run against mocked sockets/HTTP responses or real temp files — no live network calls anywhere, so they pass in CI or fully offline exactly the same way.

---

## 🛣️ Roadmap

| Idea | Status |
|---|---|
| Multi-page crawl (same host only, capped) | 💭 planned |
| IPv6-aware DNS/connect reporting | 💭 planned |
| Core Web Vitals — heuristic estimate only, not real LCP/CLS (needs a real browser for that) | 💭 low priority |
| Screenshot capture — desktop only, won't run in Termux | 💭 low priority |

---

## 🤝 Contributing

Issues and PRs welcome! Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the test workflow and PR rules. One rule: PRs that remove the load-test safety caps or add multi-target/subdomain scanning will be declined — see [`ETHICAL_USE.md`](ETHICAL_USE.md) for why. Security issues go to [`SECURITY.md`](SECURITY.md), not the public issue tracker.

---

## 👤 Author

**Tahsan Ahmed** — [github.com/tahsan2544](https://github.com/tahsan2544)

## 📄 License

MIT — see [LICENSE](LICENSE).
