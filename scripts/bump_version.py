#!/usr/bin/env python3
"""
Bumps the patch version in vitalyze/__init__.py automatically.

Called by githooks/pre-commit so every commit ships with an incremented
version number without having to remember to do it by hand. Pure Python
(no shell-specific syntax) so it runs identically on Linux, macOS, Windows,
and Termux.

Run manually if you ever want to bump without committing:
    python3 scripts/bump_version.py
"""

import re
import pathlib
import sys

INIT_FILE = pathlib.Path(__file__).resolve().parent.parent / "vitalyze" / "__init__.py"
VERSION_PATTERN = re.compile(r'__version__ = "(\d+)\.(\d+)\.(\d+)"')


def bump_patch(version: str) -> str:
    """'2.4.0' -> '2.4.1'. Only the patch number moves — a pre-commit hook
    bumping major/minor automatically would be actively misleading, since
    those numbers are meant to signal something about the size of a change,
    not just that a commit happened."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def main() -> int:
    if not INIT_FILE.is_file():
        print(f"[bump_version] {INIT_FILE} not found — skipping.")
        return 0

    content = INIT_FILE.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        print(f"[bump_version] No __version__ = \"X.Y.Z\" line found in {INIT_FILE} — skipping.")
        return 0

    old_version = match.group(0).split('"')[1]
    new_version = bump_patch(old_version)
    new_content = content[:match.start()] + f'__version__ = "{new_version}"' + content[match.end():]
    INIT_FILE.write_text(new_content, encoding="utf-8")
    print(f"[bump_version] {old_version} -> {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
