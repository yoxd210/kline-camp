"""副图公式清单：读 `formulas.json`（你自己的），没有就用 `formulas.example.json`。

为什么放文件而不是写死在代码里：
  - 每次打开不用重新填，改一下 json 就生效
  - 你自己的战法指标写在 `formulas.json`，那个文件被 .gitignore 忽略，不会进仓库

格式（两种键名都认，中文更顺手）：

    {"items": [
      {"名称": "价格偏离 20 日线%", "公式": "(CLOSE-MA(CLOSE,20))/MA(CLOSE,20)*100"},
      {"name": "...", "formula": "...", "hint": "可选说明"}
    ]}

也可以用环境变量 `KLINE_FORMULAS` 指到别的文件。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_FILE = Path(os.getenv("KLINE_FORMULAS", ROOT / "formulas.json"))
EXAMPLE_FILE = ROOT / "formulas.example.json"

# 兜底：连示例文件都缺了也能跑
FALLBACK: list[dict] = [
    {"id": "ma_gap", "name": "价格偏离 20 日均线（%）",
     "formula": "(CLOSE - MA(CLOSE,20)) / MA(CLOSE,20) * 100", "hint": "0 轴上方=在均线上方"},
    {"id": "vol_ratio", "name": "量比（5 日）", "formula": "VOLUME / MA(VOLUME,5)", "hint": "1 以上=放量"},
    {"id": "ema_diff", "name": "双均线差（EMA12 − EMA26）",
     "formula": "EMA(CLOSE,12) - EMA(CLOSE,26)", "hint": "零轴上下与拐头"},
]

DEFAULT_NAME = "价格偏离 20 日均线（%）"

_cache: dict = {"mtime": 0.0, "path": None, "items": None}


def _pick_file() -> Path | None:
    if USER_FILE.exists():
        return USER_FILE
    if EXAMPLE_FILE.exists():
        return EXAMPLE_FILE
    return None


def _normalize(raw: object) -> list[dict]:
    items = raw.get("items") if isinstance(raw, dict) else raw
    out: list[dict] = []
    for i, it in enumerate(items or []):
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("名称") or "").strip()
        formula = str(it.get("formula") or it.get("公式") or "").strip()
        if not formula:
            continue
        out.append({
            "id": str(it.get("id") or f"f{i + 1}"),
            "name": name or f"公式 {i + 1}",
            "formula": formula,
            "hint": str(it.get("hint") or it.get("说明") or "").strip(),
        })
    return out


def load() -> list[dict]:
    """读清单（按 mtime 缓存，改完文件刷新页面就生效）。"""
    path = _pick_file()
    if path is None:
        return list(FALLBACK)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return list(FALLBACK)
    if _cache["items"] is not None and _cache["mtime"] == mtime and _cache["path"] == path:
        return _cache["items"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return list(FALLBACK)
    items = _normalize(raw)
    if not items:
        return list(FALLBACK)
    _cache.update({"mtime": mtime, "path": path, "items": items})
    return items


def default_id() -> str:
    items = load()
    for it in items:
        if it["name"] == DEFAULT_NAME:
            return it["id"]
    return items[0]["id"]


def remove(name: str) -> list[dict]:
    """从 formulas.json 里删掉一条（同名）。没有用户文件就什么都不做。"""
    name = (name or "").strip()
    if not USER_FILE.exists():
        raise ValueError("还没有 formulas.json，没什么可删的")
    try:
        items = _normalize(json.loads(USER_FILE.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"formulas.json 读不了：{exc}") from exc
    kept = [x for x in items if x["name"] != name]
    if len(kept) == len(items):
        raise ValueError(f"formulas.json 里没有「{name}」")
    payload = {"items": [{"名称": x["name"], "公式": x["formula"], **({"说明": x["hint"]} if x.get("hint") else {})} for x in kept]}
    USER_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _cache["items"] = None
    return load()


def is_user_file(path: Path | None = None) -> bool:
    """这条公式是不是存在你自己的 formulas.json 里（示例不算）。"""
    return (path or USER_FILE).exists()


def save(name: str, formula: str, hint: str = "") -> list[dict]:
    """把一条公式写进 formulas.json（同名覆盖）。返回写入后的清单。"""
    name = (name or "").strip()
    formula = (formula or "").strip()
    if not name:
        raise ValueError("要给公式起个名字")
    if not formula:
        raise ValueError("公式是空的")

    path = USER_FILE
    items: list[dict] = []
    if path.exists():
        try:
            items = _normalize(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            items = []
    if not items:
        # 第一次写：把当前能看到的（示例）也带上，别让用户只剩自己那一条
        items = [dict(x) for x in load()]

    replaced = False
    for it in items:
        if it["name"] == name:
            it["formula"] = formula
            it["hint"] = hint or it.get("hint", "")
            replaced = True
            break
    if not replaced:
        items.append({"id": f"u{len(items) + 1}", "name": name, "formula": formula, "hint": hint})

    # 落盘用中文键：这个文件是给人手改的
    payload = {
        "items": [
            {"名称": x["name"], "公式": x["formula"], **({"说明": x["hint"]} if x.get("hint") else {})}
            for x in items
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _cache["items"] = None          # 让下次 load 重新读
    return load()
