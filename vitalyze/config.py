"""Load and save Vitalyze run configuration as JSON, so a target URL and
preferred flags can be reused across scans instead of retyped every time.

Deliberately JSON, not YAML — keeps the tool at zero dependencies beyond
`requests`, and avoids a config format with its own parsing quirks.
"""

import json
import os

DEFAULT_CONFIG_FILENAME = "vitalyze.config.json"

# Must match main.py's argparse dest names exactly (dashes become
# underscores: --load-test -> load_test) so set_defaults(**data) lines up.
CONFIGURABLE_KEYS = [
    "url", "runs", "skip", "load_test", "confirm_authorized",
    "concurrency", "requests", "output", "save",
    "history_db", "no_history", "trend", "no_color",
    "webhook", "webhook_format", "alert_threshold", "alert_always",
]


def load(path: str) -> dict:
    """Load a config file. Returns {} if the path is falsy or doesn't exist.

    Raises ValueError on invalid JSON, a non-object top level, or unknown keys
    — better to fail loudly than silently ignore a typo'd setting.
    """
    if not path or not os.path.isfile(path):
        return {}

    with open(path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Config file {path} is not valid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a JSON object, not a {type(data).__name__}")

    unknown = set(data.keys()) - set(CONFIGURABLE_KEYS)
    if unknown:
        raise ValueError(
            f"Unknown config key(s) in {path}: {', '.join(sorted(unknown))}. "
            f"Valid keys: {', '.join(CONFIGURABLE_KEYS)}"
        )

    return data


def save(path: str, values: dict) -> None:
    """Save the given values (filtered to known, non-default keys) as a
    config file. Silently drops keys that aren't in CONFIGURABLE_KEYS."""
    filtered = {
        k: v for k, v in values.items()
        if k in CONFIGURABLE_KEYS and v not in (None, False, [], "")
    }
    with open(path, "w") as f:
        json.dump(filtered, f, indent=2)
        f.write("\n")
