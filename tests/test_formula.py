"""公式引擎测试：语法、函数语义、错误提示，以及"不碰未来"的保证。"""

from __future__ import annotations

import pandas as pd
import pytest

from klinecamp import formula


def bars(n: int = 40) -> pd.DataFrame:
    close = [10 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="D"),
        "open": [c - 0.1 for c in close],
        "high": [c + 0.2 for c in close],
        "low": [c - 0.2 for c in close],
        "close": close,
        "volume": [1000 + i * 10 for i in range(n)],
        "amount": [1e6] * n,
    })


def test_ma_of_close():
    s = formula.evaluate("MA(CLOSE,5)", bars())
    assert s.iloc[:4].isna().all()          # 前 4 根凑不满 5 根
    assert s.iloc[4] == pytest.approx((10 + 10.5 + 11 + 11.5 + 12) / 5)


def test_field_aliases():
    df = bars()
    assert formula.evaluate("C", df).tolist() == formula.evaluate("CLOSE", df).tolist()


def test_arithmetic_precedence():
    s = formula.evaluate("CLOSE - MA(CLOSE,5)", bars())
    assert s.iloc[-1] == pytest.approx(29.5 - (27.5 + 28 + 28.5 + 29 + 29.5) / 5)


def test_ref_and_sum():
    df = bars()
    assert formula.evaluate("REF(CLOSE,1)", df).iloc[-1] == pytest.approx(df["close"].iloc[-2])
    assert formula.evaluate("SUM(VOLUME,3)", df).iloc[-1] == pytest.approx(
        df["volume"].iloc[-3:].sum()
    )


def test_cross_detects_up_cross():
    df = bars(10)
    s = formula.evaluate("CROSS(CLOSE, REF(CLOSE,1))", df)
    assert s.iloc[0] == 0 and s.iloc[-1] == 0      # 单调上涨，永远不会"上穿"自己


def test_hhv_llv():
    df = bars()
    assert formula.evaluate("HHV(HIGH,5)", df).iloc[-1] == pytest.approx(df["high"].iloc[-5:].max())
    assert formula.evaluate("LLV(LOW,5)", df).iloc[-1] == pytest.approx(df["low"].iloc[-5:].min())


def test_unknown_function_message():
    with pytest.raises(formula.FormulaError, match="不支持的函数"):
        formula.evaluate("FOO(CLOSE,1)", bars())


def test_wrong_arity():
    with pytest.raises(formula.FormulaError, match="需要 2 个参数"):
        formula.evaluate("MA(CLOSE)", bars())


def test_unclosed_paren():
    with pytest.raises(formula.FormulaError, match="没写完"):
        formula.evaluate("(CLOSE", bars())


def test_integer_second_arg():
    with pytest.raises(formula.FormulaError, match="正整数"):
        formula.evaluate("MA(CLOSE,0)", bars())


def test_only_visible_bars_are_used():
    """公式只吃传进来的那一段：截断后结果不该包含后面的数据。"""
    df = bars(40)
    full = formula.evaluate("CLOSE", df)
    part = formula.evaluate("CLOSE", df.iloc[:20])
    assert len(part) == 20 and part.iloc[-1] == full.iloc[19]
