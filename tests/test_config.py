"""Tests for JSON config file load/save (round-trip, validation)."""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vitalyze import config as config_module


def test_load_missing_file_returns_empty_dict():
    assert config_module.load("/tmp/definitely-does-not-exist-12345.json") == {}


def test_load_empty_path_returns_empty_dict():
    assert config_module.load("") == {}
    assert config_module.load(None) == {}


def test_save_then_load_round_trip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vitalyze.config.json")
        config_module.save(path, {"url": "https://example.com", "runs": 10, "skip": ["seo"]})
        loaded = config_module.load(path)
        assert loaded == {"url": "https://example.com", "runs": 10, "skip": ["seo"]}


def test_save_drops_default_falsy_values():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.json")
        config_module.save(path, {
            "url": "https://example.com",
            "load_test": False,
            "skip": [],
            "save": None,
            "runs": 5,
        })
        loaded = config_module.load(path)
        assert loaded == {"url": "https://example.com", "runs": 5}


def test_save_drops_unknown_keys():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.json")
        config_module.save(path, {"url": "https://example.com", "not_a_real_setting": "x"})
        loaded = config_module.load(path)
        assert "not_a_real_setting" not in loaded


def test_load_rejects_unknown_keys():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.json")
        with open(path, "w") as f:
            json.dump({"url": "https://example.com", "totally_bogus_key": 1}, f)
        try:
            config_module.load(path)
            assert False, "expected ValueError"
        except ValueError as e:
            assert "totally_bogus_key" in str(e)


def test_load_rejects_invalid_json():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        try:
            config_module.load(path)
            assert False, "expected ValueError"
        except ValueError as e:
            assert "not valid JSON" in str(e)


def test_load_rejects_non_object_json():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.json")
        with open(path, "w") as f:
            json.dump(["not", "an", "object"], f)
        try:
            config_module.load(path)
            assert False, "expected ValueError"
        except ValueError as e:
            assert "JSON object" in str(e)


if __name__ == "__main__":
    import inspect
    funcs = [f for name, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction)
             if name.startswith("test_")]
    for f in funcs:
        f()
        print(f"PASS: {f.__name__}")
    print(f"{len(funcs)}/{len(funcs)} passed")
