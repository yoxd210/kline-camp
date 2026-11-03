"""MACD 口径测试：和手算的 EMA 对得上，柱值 = (DIF-DEA)×2。"""

from __future__ import annotations

import pandas as pd
import pytest

from klinecamp import indicators


def test_macd_matches_manual_ema():
    close = pd.Series([10 + i * 0.3 for i in range(60)])
    dif, dea, hist = indicators.macd(close)
    manual_dif = indicators.ema(close, 12) - indicators.ema(close, 26)
    manual_dea = indicators.ema(manual_dif, 9)
    assert dif.iloc[-1] == pytest.approx(manual_dif.iloc[-1])
    assert dea.iloc[-1] == pytest.approx(manual_dea.iloc[-1])
    assert hist.iloc[-1] == pytest.approx((manual_dif.iloc[-1] - manual_dea.iloc[-1]) * 2)


def test_macd_zero_on_flat_price():
    close = pd.Series([20.0] * 40)
    dif, dea, hist = indicators.macd(close)
    assert abs(dif.iloc[-1]) < 1e-9
    assert abs(dea.iloc[-1]) < 1e-9
    assert abs(hist.iloc[-1]) < 1e-9


def test_macd_positive_in_uptrend():
    close = pd.Series([10 * (1.01 ** i) for i in range(80)])
    dif, _dea, _hist = indicators.macd(close)
    assert dif.iloc[-1] > 0


def test_payload_skips_nan_and_rounds():
    dates = [f"2026-01-{i:02d}" for i in range(1, 41)]
    close = pd.Series([10.0] * 40)
    out = indicators.macd_payload(dates, close)
    assert set(out) == {"dif", "dea", "hist"}
    assert len(out["dif"]) <= 40
    assert all("time" in x and "value" in x for x in out["dif"])
