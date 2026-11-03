"""全市场窗口扫描：给「条件选股」用。

为什么不用逐只读：4600 只票、每只一个 parquet，逐只 open 一遍要十几分钟。
这里用 pyarrow.dataset 对整个目录做一次带谓词下推的扫描（和 pandas 的 read_parquet 不同，
它只读需要的列、只读时间窗内的行），实测 1~3 秒。
"""

from __future__ import annotations

import pandas as pd
import pyarrow.dataset as ds

from klinecamp import config

COLS = ["code", "date", "open", "high", "low", "close", "volume", "amount"]

_WINDOW_CACHE: dict = {"days": 0, "df": None}


def _dataset() -> ds.Dataset:
    return ds.dataset(str(config.BARS_DIR), format="parquet")


def last_date() -> str:
    """全市场最新一个交易日。"""
    table = _dataset().to_table(columns=["date"])
    col = table.column("date").to_pandas()
    return str(pd.to_datetime(col).max().date())


def window(days: int = 140) -> pd.DataFrame:
    """最近 `days` 个交易日（日历日按 1.6 倍放宽）的全市场日线，按日期升序。"""
    hit = _WINDOW_CACHE
    if hit["df"] is not None and hit["days"] == days:
        return hit["df"]

    end = pd.Timestamp(last_date())
    # 交易日 ≈ 日历日的 0.7，多留 1.5 倍余量，再在各股内部按 tail(days) 截
    start = end - pd.Timedelta(days=int(days * 1.6) + 30)
    table = _dataset().to_table(
        columns=COLS,
        filter=(ds.field("date") >= start) & (ds.field("date") <= end),
    )
    df = table.to_pandas()
    if df.empty:
        raise RuntimeError(f"{config.BARS_DIR} 里读不到日线")
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    keep = df.groupby("code").tail(days)
    hit["df"] = keep.reset_index(drop=True)
    hit["days"] = days
    return hit["df"]
