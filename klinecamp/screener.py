"""条件选股：先按技术条件筛出一池子票，再从里面随机抽一只来练。

为什么不直接全市场随机：随机抽到的是「没有形态」的票，练不出东西。
先过滤出「今天有信号」的票，再从里面随机，练的每一局都是有事发生的。

条件是写死的几条经典形态（见 CONDITIONS），全部纯本地计算。
想加自己的条件，往 CONDITIONS 里加一条、在 compute() 里写对应判断即可。
"""

from __future__ import annotations

import pandas as pd

from klinecamp import window

# id → (显示名, 一句话说明)
CONDITIONS: dict[str, tuple[str, str]] = {
    "breakout20": ("放量突破 20 日线", "收盘上穿 MA20，且成交额 ≥ 前 5 日均额 ×1.3"),
    "pullback20": ("缩量回踩 20 日线", "最低价摸到 MA20 附近但收在线上，成交量缩到 5 日均量 0.8 倍以下"),
    "limit_up5": ("近 5 日有涨停", "5 个交易日内至少一根涨幅 ≥ 9.5%"),
    "strong_lowvol": ("强势低波", "20 日涨幅 >15%，且 ATR 占价格 <5%"),
}

_CACHE: dict[str, list[str]] = {}
_WINDOW_DAYS = 140


def _metrics(df: pd.DataFrame) -> pd.DataFrame:
    """每只票一行：MA20、5 日均额/均量、20 日涨幅、ATR%。"""
    g = df.sort_values(["code", "date"]).copy()
    by = g.groupby("code", sort=False)
    g["ma20"] = by["close"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    g["ma20_prev"] = by["ma20"].shift(1) if False else g.groupby("code")["ma20"].shift(1)
    g["amt5"] = by["amount"].rolling(5, min_periods=3).mean().reset_index(level=0, drop=True)
    g["vol5"] = by["volume"].rolling(5, min_periods=3).mean().reset_index(level=0, drop=True)
    g["close20"] = g.groupby("code")["close"].shift(20)

    last = g.groupby("code", sort=False).tail(1).copy()
    prev = g.groupby("code", sort=False).nth(-2).set_index("code")
    last = last.set_index("code")
    last["close_prev"] = prev["close"].reindex(last.index)
    last["ma20_prev"] = prev["ma20"].reindex(last.index)
    last["ret20"] = last["close"] / last["close20"] - 1

    # 近 5 日最大单日涨幅
    g["chg"] = g.groupby("code")["close"].pct_change()
    max5 = g.groupby("code")["chg"].apply(lambda s: s.tail(5).max())
    last["max5"] = max5.reindex(last.index)

    # ATR%（14 日）
    tr = pd.concat(
        [
            (g["high"] - g["low"]),
            (g["high"] - g.groupby("code")["close"].shift(1)).abs(),
            (g["low"] - g.groupby("code")["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    g["tr"] = tr
    g["atr14"] = g.groupby("code")["tr"].transform(lambda s: s.rolling(14, min_periods=5).mean())
    last["atr_pct"] = g.groupby("code")["atr14"].last() / last["close"]
    return last


def compute(df: pd.DataFrame, cond: str) -> list[str]:
    """纯函数：给一份窗口数据，返回命中的代码（方便单测）。"""
    if cond not in CONDITIONS:
        raise ValueError(f"未知条件：{cond}")
    m = _metrics(df)
    if cond == "breakout20":
        hit = m[(m["close"] > m["ma20"]) & (m["close_prev"] <= m["ma20_prev"]) & (m["amount"] >= m["amt5"] * 1.3)]
    elif cond == "pullback20":
        hit = m[
            (m["low"] <= m["ma20"] * 1.02)
            & (m["close"] >= m["ma20"])
            & (m["volume"] <= m["vol5"] * 0.8)
        ]
    elif cond == "limit_up5":
        hit = m[m["max5"] >= 0.095]
    elif cond == "strong_lowvol":
        hit = m[(m["ret20"] >= 0.15) & (m["atr_pct"] <= 0.05)]
    else:  # pragma: no cover
        hit = m.iloc[0:0]
    return sorted(hit.index.astype(str).tolist())


def pool(cond: str) -> list[str]:
    """命中池（进程内缓存）。"""
    if cond in _CACHE:
        return _CACHE[cond]
    df = window.window(_WINDOW_DAYS)
    codes = compute(df, cond)
    _CACHE[cond] = codes
    return codes

