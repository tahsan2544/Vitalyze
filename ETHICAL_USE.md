# Responsible Use Policy

Vitalyze includes a load-testing feature that sends concurrent HTTP requests
to a target. This section is not boilerplate — please actually read it.

## Only test what you own or are authorized to test

Running concurrent/automated traffic against a website you don't own or
don't have **explicit written permission** to test can be:

- A violation of the target's Terms of Service or Acceptable Use Policy
- A violation of computer-crime laws in your jurisdiction (e.g. the U.S.
  Computer Fraud and Abuse Act, UK Computer Misuse Act, or equivalents
  elsewhere), even if no data is stolen and nothing is "hacked"
- Grounds for your own hosting provider or ISP to suspend your account,
  since outbound abuse reports get attributed to you

"I was just testing performance" is not a legal or ethical shield if the
target didn't agree to be tested.

## What this tool is designed to do

- Measure response time, TLS health, security headers, and basic SEO
  hygiene for a site — read-only, single-request checks.
- Run a **capped** concurrent load test (hard limits: {MAX_CONCURRENCY}
  concurrent workers, {MAX_REQUESTS} total requests — see
  `vitalyze/load_test.py`) so you can see how your own site's infra behaves
  under modest simultaneous traffic.

## What this tool is not designed to do

- It is not a stress/DoS tool. The caps are intentional and are not meant
  to be raised by editing the source to "test harder" against something you
  don't control.
- It does not enumerate, scan, or target subdomains. Each run targets
  exactly one URL you provide.
- It has no distributed/botnet mode and never will.

## Before you run `--load-test`

1. Confirm you own the domain, or have the domain owner's written sign-off.
2. If the site sits behind a CDN/host with shared infrastructure (e.g. a
   $5/mo shared host), a "small" load test can still degrade service for
   other tenants — check your hosting provider's testing policy first.
3. Run it against a staging environment where possible, not production.

If you want to responsibly test infrastructure you don't fully control
(e.g. a client's site), get it in writing first — an email confirming
scope, dates, and rate limits is enough.
