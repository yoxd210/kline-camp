"""界面布局偏好：主图高度 / 副图高度 / 图表区宽度 / 显示哪些公式副图。

拖一次就记住，下次打开直接是这个布局（存 `layout.json`）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = Path(os.getenv("KLINE_LAYOUT", ROOT / "layout.json"))

DEFAULTS: dict = {
    "main": 460,      # 主图高度 px
    "panel": 92,      # 每块副图高度 px（成交量 / MACD / 公式 都一样高）
    "width": 1180,    # 图表区宽度 px（右侧信息栏固定 360）
    "shown": [],      # 显示哪些公式副图（名称，最多 3 个）
}

LIMITS: dict = {
    "main": (240, 900),
    "panel": (48, 300),
    "width": (720, 1700),
}

MAX_SHOWN = 3


def clamp(key: str, value: float) -> int:
    lo, hi = LIMITS.get(key, (0, 4000))
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULTS.get(key, lo)
    return max(lo, min(hi, v))


def _shown(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for x in value:
        name = str(x).strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= MAX_SHOWN:
            break
    return out


def load() -> dict:
    out = dict(DEFAULTS)
    if not FILE.exists():
        return out
    try:
        raw = json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    if not isinstance(raw, dict):
        return out
    for k in LIMITS:
        if k in raw:
            out[k] = clamp(k, raw[k])
    if "shown" in raw:
        out["shown"] = _shown(raw["shown"])
    return out


def save(patch: dict) -> dict:
    cur = load()
    patch = patch or {}
    for k in LIMITS:
        if k in patch:
            cur[k] = clamp(k, patch[k])
    if "shown" in patch:
        cur["shown"] = _shown(patch["shown"])
    FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cur
