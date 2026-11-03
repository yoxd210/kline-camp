"""规则测试：成交价、T+1、费用、结算、基准。

这些是训练营的"物理定律"，错了整局成绩都不可信，所以单独测。
"""

from __future__ import annotations

import random

import pandas as pd
import pytest

from klinecamp import config
from klinecamp.data import Case
from klinecamp.session import Session


def make_rows(n: int = 40) -> pd.DataFrame:
    """造一段确定的日线：第 0 根 10 元，每天 +1 元，方便手算。"""
    rows = []
    for i in range(n):
        close = 10.0 + i
        rows.append({
            "date": f"2026-01-{i + 1:02d}",
            "open": close - 0.5,
            "high": close + 0.5,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
            "amount": close * 1000,
        })
    return pd.DataFrame(rows)


def make_session(warmup: int = 5, cash: float = 100000.0) -> Session:
    rows = make_rows()
    case = Case("600000", "测试", "测试行业", warmup, len(rows), [str(d) for d in rows["date"]])
    return Session(case=case, rows=rows, cash0=cash, cash=cash)


def test_open_hides_future():
    s = make_session(warmup=5)
    assert len(s.visible()) == 5
    assert s.state()["date"] == "2026-01-05"


def test_buy_fills_at_next_open():
    s = make_session(warmup=5)
    s.order("buy", 100)
    assert s.state()["shares"] == 0                    # 还没成交
    s.step()                                            # 走到第 6 根
    # 第 6 根 open = 15 - 0.5 = 14.5
    assert s.shares == 100
    trade = s.trades[-1]
    assert trade.price == pytest.approx(14.5)
    assert trade.fee == pytest.approx(max(config.MIN_COMMISSION, 14.5 * 100 * config.COMMISSION_RATE))


def test_t_plus_one_blocks_same_day_sell():
    s = make_session(warmup=5)
    s.order("buy", 100)
    s.step()
    with pytest.raises(ValueError, match="T\\+1"):
        s.order("sell", 100)
    s.step()                                            # 再走一根才能卖
    s.order("sell", 100)
    assert s.state()["pending"]["side"] == "sell"


def test_sell_charges_stamp_tax():
    s = make_session(warmup=5)
    s.order("buy", 100)
    s.step()
    s.step()
    s.order("sell", 100)
    s.step()
    sell = s.trades[-1]
    assert sell.tax == pytest.approx(sell.price * 100 * config.STAMP_TAX)
    assert sell.pnl is not None


def test_cash_never_negative():
    s = make_session(warmup=5, cash=1000.0)
    with pytest.raises(ValueError, match="现金不够"):
        s.order("buy", 1000)
    assert s.cash == 1000.0


def test_finish_stats_and_benchmarks():
    s = make_session(warmup=5)
    s.order("buy", 100)
    s.step()
    while s.state()["bars_left"] > 0:
        s.step()
    r = s.finish()
    assert r["bars_played"] == len(s.rows) - 5
    assert r["benchmarks"]["buy_hold_pct"] > 0
    assert r["equity_end"] > 0
    assert 0 <= r["max_drawdown_pct"] <= 100


def test_pending_blocks_second_order():
    s = make_session(warmup=5)
    s.order("buy", 100)
    with pytest.raises(ValueError, match="还没成交"):
        s.order("buy", 100)


@pytest.mark.skipif(not config.META_FILE.exists(), reason="本机没有行情数据，跳过（用 make_demo_data 造一份就能跑）")
def test_random_case_returns_playable_game():
    case = __import__("klinecamp.data", fromlist=["x"]).random_case(random.Random(7))
    assert case.start_index >= config.WARMUP_BARS
    assert case.future_bars >= config.MIN_FUTURE
