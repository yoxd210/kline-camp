"""内置副图指标：只做 MACD（成交量前端直接画 bars 里的 volume）。

口径用国内行情软件最常见的那套：
    DIF  = EMA(close,12) - EMA(close,26)
    DEA  = EMA(DIF, 9)
    MACD = (DIF - DEA) * 2        ← 柱状图的值

和同花顺/东财的数值一致（有些国外软件柱是 DIF-DEA，不乘 2，这里按国内习惯）。
"""

from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """返回 (dif, dea, hist)。hist 已经乘过 2。"""
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def macd_payload(dates: list[str], close: pd.Series) -> dict:
    """转成前端要的 [{time, value}...]（NaN 跳过，图上自然断开）。"""
    dif, dea, hist = macd(close)

    def pack(s: pd.Series) -> list[dict]:
        out = []
        for d, v in zip(dates, s):
            if v != v or v is None:
                continue
            out.append({"time": d, "value": round(float(v), 4)})
        return out

    return {"dif": pack(dif), "dea": pack(dea), "hist": pack(hist)}
