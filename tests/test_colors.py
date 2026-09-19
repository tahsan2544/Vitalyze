"""Tests for color helpers — verifies both the enabled (ANSI codes present)
and disabled (plain text passthrough) states explicitly, rather than relying
on whatever state stdout happens to be in during a test run."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import colors


def test_disabled_returns_plain_text():
    colors.disable()
    assert colors.red("hello") == "hello"
    assert colors.green("hello") == "hello"
    assert colors.bold("hello") == "hello"


def test_enabled_wraps_with_ansi_codes():
    colors.enable()
    try:
        result = colors.red("hello")
        assert result != "hello"
        assert "hello" in result
        assert "\033[" in result
        assert result.endswith(colors._CODES["reset"])
    finally:
        colors.disable()


def test_score_color_thresholds():
    colors.enable()
    try:
        assert "32m" in colors.score_color(80)   # green
        assert "32m" in colors.score_color(100)
        assert "33m" in colors.score_color(50)   # yellow
        assert "33m" in colors.score_color(79)
        assert "31m" in colors.score_color(49)   # red
        assert "31m" in colors.score_color(0)
    finally:
        colors.disable()


def test_score_color_none_is_dim_not_a_crash():
    colors.enable()
    try:
        result = colors.score_color(None)
        assert "None" in result
    finally:
        colors.disable()


def test_ok_bad_warn_include_icons():
    colors.disable()
    assert colors.CHECK in colors.ok("fine")
    assert colors.CROSS in colors.bad("broken")
    assert colors.WARN in colors.warn("careful")


def test_enabled_reflects_state():
    colors.enable()
    assert colors.enabled() is True
    colors.disable()
    assert colors.enabled() is False


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
