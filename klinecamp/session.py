"""一局训练的规则引擎：逐根推进、下一根开盘成交、T+1、佣金印花税、结算与对照。

设计原则（和项目 README 里写的一样）：
  - **不许偷看未来**：`visible()` 永远只按 cursor 截断
  - **下单不可即时成交**：买单/卖单排到下一根的开盘价成交，和真实盘后决定、次日执行一致
  - **T+1**：当根买入的股数，下一根才能卖
  - **结算用代码算**：收益、回撤、胜率、对照基准全在这里算，不信任何模型的措辞
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from klinecamp import config
from klinecamp.data import Case


@dataclass
class Trade:
    date: str
    side: str            # buy / sell
    shares: int
    price: float
    fee: float
    tax: float
    pnl: float | None = None   # 卖出时按移动平均成本算

    def as_dict(self) -> dict:
        return {
            "date": self.date, "side": self.side, "shares": self.shares,
            "price": round(self.price, 3), "fee": round(self.fee, 2),
            "tax": round(self.tax, 2),
            "pnl": None if self.pnl is None else round(self.pnl, 2),
        }


@dataclass
class Session:
    case: Case
    rows: pd.DataFrame
    cash0: float = config.DEFAULT_CASH
    cash: float = config.DEFAULT_CASH
    cursor: int = 0
    shares: int = 0
    cost: float = 0.0                 # 持仓移动平均成本
    locked: int = 0                   # 当根买入、T+1 才能卖的股数
    pending: tuple[str, int] | None = None
    trades: list[Trade] = field(default_factory=list)
    curve: list[dict] = field(default_factory=list)
    finished: bool = False

    # ---------------------------------------------------------------- 视图
    def __post_init__(self) -> None:
        self.cursor = self.case.start_index - 1      # 开局只看到 warmup 那段
        self.record()

    def bar(self) -> pd.Series:
        return self.rows.iloc[self.cursor]

    def visible(self) -> pd.DataFrame:
        return self.rows.iloc[: self.cursor + 1]

    def equity(self) -> float:
        return self.cash + self.shares * float(self.bar()["close"])

    def record(self) -> None:
        self.curve.append({"date": str(self.bar()["date"]), "equity": round(self.equity(), 2)})

    def state(self) -> dict:
        bar = self.bar()
        close = float(bar["close"])
        return {
            "date": str(bar["date"]),
            "cursor": self.cursor - self.case.start_index,   # 已经练了几根
            "bars_left": self.case.future_bars - (self.cursor - self.case.start_index + 1),
            "price": round(close, 2),
            "cash": round(self.cash, 2),
            "shares": self.shares,
            "locked": self.locked,
            "cost": round(self.cost, 3) if self.shares else None,
            "market_value": round(self.shares * close, 2),
            "equity": round(self.equity(), 2),
            "return_pct": round((self.equity() / self.cash0 - 1) * 100, 2),
            "pending": None if not self.pending else {"side": self.pending[0], "shares": self.pending[1]},
            "trades": len(self.trades),
            "finished": self.finished,
        }

    # ---------------------------------------------------------------- 推进
    def step(self) -> dict:
        if self.finished:
            raise ValueError("这一局已经结束了")
        if self.cursor + 1 >= len(self.rows):
            raise ValueError("已经走到最后一根，没有下一根了")
        self.cursor += 1
        self.locked = 0
        if self.pending:
            side, shares = self.pending
            self.pending = None
            self._fill(side, shares)
        self.record()
        return self.state()

    def _fill(self, side: str, shares: int) -> None:
        price = float(self.bar()["open"])
        amount = price * shares
        fee = max(config.MIN_COMMISSION, amount * config.COMMISSION_RATE)
        if side == "buy":
            self.cash -= amount + fee
            new_cost = (self.cost * self.shares + amount + fee) / (self.shares + shares)
            self.shares += shares
            self.cost = new_cost
            self.locked = shares                       # T+1
            self.trades.append(Trade(str(self.bar()["date"]), "buy", shares, price, fee, 0.0))
        else:
            tax = amount * config.STAMP_TAX
            pnl = (price - self.cost) * shares - fee - tax
            self.cash += amount - fee - tax
            self.shares -= shares
            if self.shares == 0:
                self.cost = 0.0
            self.trades.append(Trade(str(self.bar()["date"]), "sell", shares, price, fee, tax, pnl))

    # ---------------------------------------------------------------- 下单
    def order(self, side: str, shares: int) -> dict:
        side = str(side or "").lower()
        if side not in ("buy", "sell"):
            raise ValueError("方向只能是 buy / sell")
        shares = int(shares)
        if shares <= 0:
            raise ValueError("股数必须大于 0")
        if side == "buy" and shares % 100:
            raise ValueError("买入必须是 100 股（一手）的整数倍")
        if self.finished:
            raise ValueError("这一局已经结束了")
        if self.pending:
            raise ValueError("上一笔还没成交（下一根开盘才成交），不能连续下单")

        est = float(self.bar()["close"])
        if side == "buy":
            need = est * shares * 1.01 + config.MIN_COMMISSION
            if need > self.cash:
                raise ValueError(f"现金不够：大约需要 {need:,.0f}，手上 {self.cash:,.0f}")
        else:
            sellable = self.shares - self.locked
            if shares > sellable:
                raise ValueError(
                    f"可卖 {sellable} 股（持仓 {self.shares}，其中 {self.locked} 股是今天买的，T+1 不能卖）"
                )
        self.pending = (side, shares)
        return self.state()

    def cancel(self) -> dict:
        self.pending = None
        return self.state()

    # ---------------------------------------------------------------- 结算
    def finish(self) -> dict:
        self.finished = True
        last_close = float(self.bar()["close"])
        start_close = float(self.rows.iloc[self.case.start_index]["close"])
        eq = [c["equity"] for c in self.curve]
        peak, mdd = eq[0], 0.0
        for v in eq:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak if peak else 0.0)

        sells = [t for t in self.trades if t.side == "sell" and t.pnl is not None]
        wins = [t for t in sells if t.pnl > 0]
        return {
            "code": self.case.code,
            "name": self.case.name,
            "industry": self.case.industry,
            "start_date": self.case.dates[self.case.start_index],
            "end_date": str(self.bar()["date"]),
            "bars_played": self.cursor - self.case.start_index + 1,
            "cash0": round(self.cash0, 2),
            "equity_end": round(self.equity(), 2),
            "return_pct": round((self.equity() / self.cash0 - 1) * 100, 2),
            "max_drawdown_pct": round(mdd * 100, 2),
            "trades": [t.as_dict() for t in self.trades],
            "round_trips": len(sells),
            "win_rate": round(len(wins) / len(sells) * 100, 1) if sells else None,
            "avg_win": round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0.0,
            "avg_loss": round(
                sum(t.pnl for t in sells if t.pnl <= 0) / max(1, len(sells) - len(wins)), 2
            ) if sells else 0.0,
            "benchmarks": {
                "buy_hold_pct": round((last_close / start_close - 1) * 100, 2),
                "ma20_pct": round(self._ma20_benchmark() * 100, 2),
            },
            "hidden": {"code": self.case.code, "name": self.case.name},
        }

    def _ma20_benchmark(self) -> float:
        """对照基准：收盘在 MA20 上方就满仓，跌破就空仓（用前一日信号，次日开盘换手）。"""
        df = self.rows.iloc[: self.cursor + 1].copy()
        df["ma20"] = df["close"].rolling(20).mean()
        seg = df.iloc[self.case.start_index:]
        cash, shares = 1.0, 0.0
        for i in range(len(seg)):
            row = seg.iloc[i]
            if pd.isna(row["ma20"]):
                continue
            want = row["close"] > row["ma20"]
            if want and shares == 0:
                shares, cash = cash / row["close"], 0.0
            elif not want and shares > 0:
                cash, shares = shares * row["close"], 0.0
        return cash + shares * float(seg["close"].iloc[-1]) - 1.0
