"""Tests for scripts/bump_version.py — the logic the pre-commit hook runs."""

import sys
import os
import tempfile
import pathlib

# scripts/ isn't part of the vitalyze package (it's a dev tool, not shipped
# functionality), so it needs its own path entry rather than going through
# the normal `from vitalyze import ...` pattern the other tests use.
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import bump_version


def test_bump_patch_basic():
    assert bump_version.bump_patch("2.4.0") == "2.4.1"


def test_bump_patch_double_digit_rollover():
    assert bump_version.bump_patch("2.4.9") == "2.4.10"


def test_bump_patch_does_not_touch_major_or_minor():
    assert bump_version.bump_patch("9.9.9") == "9.9.10"


def test_bump_patch_zero_version():
    assert bump_version.bump_patch("0.0.0") == "0.0.1"


def test_main_rewrites_file_correctly():
    with tempfile.TemporaryDirectory() as d:
        pkg_dir = pathlib.Path(d) / "vitalyze"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('"""Docstring."""\n\n__version__ = "1.2.3"\n')

        original_init_file = bump_version.INIT_FILE
        try:
            bump_version.INIT_FILE = init_file
            result = bump_version.main()
        finally:
            bump_version.INIT_FILE = original_init_file

        assert result == 0
        new_content = init_file.read_text()
        assert '__version__ = "1.2.4"' in new_content
        assert '"""Docstring."""' in new_content, "rest of the file should be untouched"


def test_main_missing_file_does_not_crash():
    original_init_file = bump_version.INIT_FILE
    try:
        bump_version.INIT_FILE = pathlib.Path("/tmp/definitely-does-not-exist-99999/__init__.py")
        result = bump_version.main()
    finally:
        bump_version.INIT_FILE = original_init_file
    assert result == 0


def test_main_missing_version_line_does_not_crash():
    with tempfile.TemporaryDirectory() as d:
        init_file = pathlib.Path(d) / "__init__.py"
        init_file.write_text('"""No version here."""\n')

        original_init_file = bump_version.INIT_FILE
        try:
            bump_version.INIT_FILE = init_file
            result = bump_version.main()
        finally:
            bump_version.INIT_FILE = original_init_file

        assert result == 0
        assert init_file.read_text() == '"""No version here."""\n'


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
