"""ANSI color helpers for console output.

Colors are on by default when stdout is a real terminal, and automatically
off when output is piped/redirected (a plain-text file shouldn't be full of
escape codes), when the NO_COLOR environment variable is set
(https://no-color.org/ — a real, respected convention), or when the user
passes --no-color. JSON/HTML output never touches this module — the raw
results dict is always plain data.
"""

import os
import sys

_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def disable() -> None:
    global _ENABLED
    _ENABLED = False


def enable() -> None:
    global _ENABLED
    _ENABLED = True


def enabled() -> bool:
    return _ENABLED


_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


def _wrap(text: str, code: str) -> str:
    if not _ENABLED:
        return text
    return f"{_CODES[code]}{text}{_CODES['reset']}"


def red(text: str) -> str: return _wrap(text, "red")
def green(text: str) -> str: return _wrap(text, "green")
def yellow(text: str) -> str: return _wrap(text, "yellow")
def blue(text: str) -> str: return _wrap(text, "blue")
def cyan(text: str) -> str: return _wrap(text, "cyan")
def magenta(text: str) -> str: return _wrap(text, "magenta")
def bold(text: str) -> str: return _wrap(text, "bold")
def dim(text: str) -> str: return _wrap(text, "dim")


def color_for_score(score):
    """Return the color function (green/yellow/red/dim) appropriate for a
    0-100 score, so a caller can apply it to more than just the bare number."""
    if score is None:
        return dim
    if score >= 80:
        return green
    if score >= 50:
        return yellow
    return red


def score_color(score) -> str:
    """Convenience: color a score's own string representation."""
    return color_for_score(score)(str(score))


# Icons — plain characters that work over any UTF-8 terminal (Linux, Windows
# Terminal/PowerShell 7+, and Termux all render these fine).
CHECK = "\u2713"   # check mark
CROSS = "\u2717"   # ballot x
WARN = "\u26a0"    # warning sign
UP = "\u2191"
DOWN = "\u2193"
FLAT = "\u2192"


def ok(text: str) -> str:
    return green(f"{CHECK} {text}")


def bad(text: str) -> str:
    return red(f"{CROSS} {text}")


def warn(text: str) -> str:
    return yellow(f"{WARN} {text}")
