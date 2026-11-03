"""条件选股的纯函数测试：用合成日线验每个条件真的按定义筛选。"""

from __future__ import annotations

import pandas as pd

from klinecamp import screener


def make_bars(code: str, closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="D")
    for i, c in enumerate(closes):
        v = (volumes[i] if volumes else 1_000_000)
        rows.append({
            "code": code, "date": dates[i],
            "open": c * 0.99, "high": c * 1.01, "low": c * 0.98, "close": c,
            "volume": v, "amount": v * c,
        })
    return pd.DataFrame(rows)


def test_breakout20_hits_when_crossing_ma20_with_volume():
    # 前 25 天横在 10 元，第 26 天拉到 11（上穿 MA20）且放量
    closes = [10.0] * 25 + [11.0]
    vols = [1_000_000] * 25 + [3_000_000]
    df = make_bars("000001", closes, vols)
    assert "000001" in screener.compute(df, "breakout20")


def test_breakout20_ignores_without_volume():
    closes = [10.0] * 25 + [11.0]
    df = make_bars("000002", closes)          # 量没放大
    assert "000002" not in screener.compute(df, "breakout20")


def test_limit_up5_detects_big_day():
    closes = [10.0] * 20 + [11.0]              # +10%
    df = make_bars("000003", closes)
    assert "000003" in screener.compute(df, "limit_up5")


def test_strong_lowvol_needs_both_trend_and_calm():
    # 稳步上涨（20 日 +20%），振幅很小
    closes = [10 + i * 0.1 for i in range(30)]
    df = make_bars("000004", closes)
    assert "000004" in screener.compute(df, "strong_lowvol")

    # 同样涨幅但每天振幅巨大
    wild = []
    for i in range(30):
        base = 10 + i * 0.1
        wild.append(base)
    df2 = make_bars("000005", wild)
    df2["high"] = df2["close"] * 1.15
    df2["low"] = df2["close"] * 0.85
    assert "000005" not in screener.compute(df2, "strong_lowvol")


def test_unknown_condition_raises():
    df = make_bars("000006", [10.0] * 25)
    try:
        screener.compute(df, "no-such-condition")
    except ValueError:
        return
    raise AssertionError("未知条件应该报错")
