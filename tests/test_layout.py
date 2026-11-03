"""布局偏好的读写与边界。"""

from __future__ import annotations

import json

import pytest

from klinecamp import layout


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    f = tmp_path / "layout.json"
    monkeypatch.setattr(layout, "FILE", f)
    return f


def test_defaults_when_no_file(sandbox):
    got = layout.load()
    assert got == layout.DEFAULTS


def test_save_and_load_roundtrip(sandbox):
    layout.save({"main": 520, "panel": 110, "width": 1000})
    got = layout.load()
    assert got["main"] == 520
    assert got["panel"] == 110
    assert got["width"] == 1000


def test_clamps_to_limits(sandbox):
    layout.save({"main": 99999, "panel": 1, "width": 10})
    got = layout.load()
    assert got["main"] == layout.LIMITS["main"][1]
    assert got["panel"] == layout.LIMITS["panel"][0]
    assert got["width"] == layout.LIMITS["width"][0]


def test_shown_list_capped_at_three(sandbox):
    layout.save({"shown": ["a", "b", "c", "d", "a"]})
    got = layout.load()
    assert got["shown"] == ["a", "b", "c"]
    assert layout.MAX_SHOWN == 3


def test_ignores_unknown_keys_and_bad_values(sandbox):
    layout.save({"nope": 1, "main": "abc"})
    got = layout.load()
    assert "nope" not in got
    assert got["main"] == layout.DEFAULTS["main"]


def test_broken_file_falls_back(sandbox):
    sandbox.write_text("{ broken", encoding="utf-8")
    assert layout.load() == layout.DEFAULTS


def test_partial_file_merges_with_defaults(sandbox):
    sandbox.write_text(json.dumps({"panel": 120}), encoding="utf-8")
    got = layout.load()
    assert got["panel"] == 120
    assert got["main"] == layout.DEFAULTS["main"]
