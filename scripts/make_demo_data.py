"""造一份**纯虚构**的示例数据，用来在没有真实行情时把项目跑起来。

价格是随机游走，代码用 3100xx 这种和真实票不会撞的号段。
不读取、不包含任何真实行情。
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

NAMES = ["示例一号", "示例二号", "示例三号", "示例四号", "示例五号"]


def gen_code(i: int) -> str:
    # 310xxx 在 A 股里不存在（创业板是 300xxx），既不会和真实票撞车，
    # 也不会被「排除北交所/科创」的规则过滤掉
    return f"310{i:03d}"


def make_bars(rng: random.Random, days: int, start_price: float) -> pd.DataFrame:
    rows = []
    price = start_price
    date = pd.Timestamp("2024-01-02")
    for _ in range(days):
        date += pd.Timedelta(days=1)
        if date.weekday() >= 5:            # 跳过周末
            date += pd.Timedelta(days=7 - date.weekday())
        drift = rng.gauss(0.0004, 0.018)
        open_ = price * (1 + rng.gauss(0, 0.006))
        close = max(1.0, price * (1 + drift))
        high = max(open_, close) * (1 + abs(rng.gauss(0, 0.008)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, 0.008)))
        vol = rng.randint(200_000, 5_000_000)
        rows.append({
            "date": date.normalize(),
            "open": round(open_, 2), "high": round(high, 2),
            "low": round(low, 2), "close": round(close, 2),
            "volume": vol, "amount": round(vol * (high + low) / 2, 2),
        })
        price = close
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo-data")
    ap.add_argument("--stocks", type=int, default=30)
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20261103)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    (out / "bars").mkdir(parents=True, exist_ok=True)

    meta = []
    for i in range(args.stocks):
        code = gen_code(i + 1)
        df = make_bars(rng, args.days, start_price=rng.uniform(6, 60))
        df.insert(0, "code", code)
        df.to_parquet(out / "bars" / f"{code}.parquet", index=False)
        meta.append({
            "code": code,
            "name": NAMES[i % len(NAMES)] + str(i + 1),
            "industry": "示例行业",
            "board": "demo",
            "market": 0,
            "price": float(df["close"].iloc[-1]),
            "pct_chg": 0.0,
            "total_mv": 1e5,
            "float_mv": 1e5,
        })

    pd.DataFrame(meta).to_parquet(out / "meta.parquet", index=False)
    print(f"已生成 {args.stocks} 只 × {args.days} 天 → {out}")
    print("用法： set KLINE_DATA_DIR=%s  &&  python run.py" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
