"""副图公式清单的读写：中文键、落盘、再读回来还在。"""

from __future__ import annotations

import json

import pytest

from klinecamp import formulas


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    user = tmp_path / "formulas.json"
    example = tmp_path / "formulas.example.json"
    example.write_text(
        json.dumps({"items": [{"名称": "示例A", "公式": "CLOSE - 1"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(formulas, "USER_FILE", user)
    monkeypatch.setattr(formulas, "EXAMPLE_FILE", example)
    monkeypatch.setitem(formulas._cache, "items", None)
    return user


def test_loads_example_when_no_user_file(sandbox):
    items = formulas.load()
    assert items and items[0]["name"] == "示例A"
    assert items[0]["formula"] == "CLOSE - 1"


def test_save_then_load_roundtrip(sandbox):
    formulas.save("我的动量", "(CLOSE - REF(CLOSE,5)) / REF(CLOSE,5) * 100")
    assert sandbox.exists()

    raw = json.loads(sandbox.read_text(encoding="utf-8"))
    assert any(x["名称"] == "我的动量" for x in raw["items"])   # 落盘用中文键，方便手改

    items = formulas.load()
    hit = [x for x in items if x["name"] == "我的动量"]
    assert hit and hit[0]["formula"].startswith("(CLOSE - REF")


def test_save_same_name_overwrites(sandbox):
    formulas.save("同名", "CLOSE")
    formulas.save("同名", "CLOSE * 2")
    items = [x for x in formulas.load() if x["name"] == "同名"]
    assert len(items) == 1
    assert items[0]["formula"] == "CLOSE * 2"


def test_save_requires_name_and_formula(sandbox):
    with pytest.raises(ValueError):
        formulas.save("", "CLOSE")
    with pytest.raises(ValueError):
        formulas.save("有名", "   ")


def test_save_keeps_examples_first_time(sandbox):
    formulas.save("我的", "CLOSE")
    items = formulas.load()
    names = [x["name"] for x in items]
    assert "我的" in names
    assert "示例A" in names


def test_broken_json_falls_back(sandbox):
    sandbox.write_text("{ 这不是 json", encoding="utf-8")
    monkeypatch_items = formulas.load()
    assert monkeypatch_items            # 不抛异常，回落到示例
