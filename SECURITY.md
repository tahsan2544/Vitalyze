# Security Policy

## Reporting a vulnerability

Report security issues in Vitalyze itself **privately** — open a draft
security advisory at
<https://github.com/tahsan2544/Vitalyze/security/advisories/new> or
contact the maintainer through GitHub. Do not open a public issue for an
unpatched vulnerability.

Include: affected version/commit, steps to reproduce, what you expected,
and what happened. Do not include real credentials, webhook URLs, or
other secrets in the report.

## Scope

**In scope** — vulnerabilities in Vitalyze itself: the CLI, JSON/HTML
report export, config and history file handling, webhook delivery, and
whether the load tester's safety behavior can be bypassed (e.g. exceeding
the documented caps, or running `--load-test` without
`--confirm-authorized`).

**Out of scope** — findings about third-party sites you point Vitalyze
at, and issues that only reproduce after editing the source to remove
the load-test safety caps.

## Load testing

`--load-test` sends concurrent traffic and is only for targets you own
or have explicit written permission to test — see
[`ETHICAL_USE.md`](ETHICAL_USE.md). Anything that lets a user exceed the
documented caps (20 workers / 500 requests / 60s duration / 30s ramp-up)
is a security issue; please report it privately.

## Supported versions

Only the latest code on the default branch receives fixes. Older
versions are not patched.
