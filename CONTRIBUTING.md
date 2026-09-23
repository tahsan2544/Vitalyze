# Contributing

Issues and PRs are welcome. Please read [`ETHICAL_USE.md`](ETHICAL_USE.md)
first — it explains why the load tester is capped the way it is.

## Running the tests

```bash
pip install -r requirements.txt
pip install pytest
python -m pytest tests/ -v
```

All tests run against mocked sockets/HTTP responses or temp files — no
live network calls. Keep new tests that way so the suite passes offline
and in CI.

## PR rules

- Keep each PR focused on one concern.
- PRs that remove or raise the load-test safety caps (20 concurrent
  workers, 500 total requests, 60-second duration, 30-second ramp-up),
  disable the auto-abort default, or add multi-target/subdomain scanning
  will be declined — see [`ETHICAL_USE.md`](ETHICAL_USE.md) for why.
- New behavior needs tests; bug fixes need a test that fails before the
  fix and passes after.
- Update `README.md` and `CHANGELOG.md` when behavior or CLI flags change.
- The pre-commit hook bumps the patch version automatically (see README)
  — no manual version edits.

## Where to report what

- Bugs and feature ideas → GitHub issues
- Security issues → [`SECURITY.md`](SECURITY.md) (report privately)
