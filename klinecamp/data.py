"""读本地日线：给训练营提供「随机一只票 + 随机一个起点」。

不联网、不依赖别的项目，只读两样东西：
    data/meta.parquet          代码 → 名称 / 行业 / 是否可交易
    data/bars/<代码>.parquet   该票的日线（code/date/open/high/low/close/volume/amount）
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

from klinecamp import config

_BARS_CACHE: dict[str, pd.DataFrame] = {}
_META_CACHE: dict = {"mtime": 0.0, "df": None}


@dataclass
class Case:
    """一局题目：哪只票、从第几根开始、能看到多少、后面还有多少。"""

    code: str
    name: str
    industry: str
    start_index: int
    total_bars: int
    dates: list[str]

    @property
    def future_bars(self) -> int:
        return self.total_bars - self.start_index

    def public(self, reveal: bool = False) -> dict:
        return {
            "code": self.code if reveal else "??????",
            "name": self.name if reveal else "盲盒",
            "industry": self.industry if reveal else "",
            "start_date": self.dates[self.start_index],
            "warmup_bars": self.start_index,
            "future_bars": self.future_bars,
        }


def meta() -> pd.DataFrame:
    """标的清单（按 mtime 缓存）。"""
    try:
        mtime = config.META_FILE.stat().st_mtime
    except OSError:
        return pd.DataFrame(columns=["code", "name", "industry"])
    if _META_CACHE["df"] is not None and _META_CACHE["mtime"] == mtime:
        return _META_CACHE["df"]
    df = pd.read_parquet(config.META_FILE)
    df["code"] = df["code"].astype(str).str.zfill(6)
    for col in ("name", "industry"):
        if col not in df:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.replace(" ", "", regex=False)
    _META_CACHE["df"] = df
    _META_CACHE["mtime"] = mtime
    return df


def load_bars(code: str) -> pd.DataFrame:
    """一只票的全部日线（按日期升序，带缓存）。"""
    code = str(code).zfill(6)
    hit = _BARS_CACHE.get(code)
    if hit is not None:
        return hit
    path = config.BARS_DIR / f"{code}.parquet"
    if not path.exists():
        raise KeyError(f"本地没有 {code} 的日线（{path}）")
    df = pd.read_parquet(path)
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    _BARS_CACHE[code] = df
    return df


def tradable_codes(limit: int = 0) -> list[str]:
    """主板/创业板，且本地有日线的代码（北交所 688/8xx/4xx 不参与训练）。"""
    df = meta()
    codes = [
        c for c in df["code"].tolist()
        if not (c.startswith("688") or c.startswith("8") or c.startswith("4") or c.startswith("9"))
    ]
    if limit:
        codes = codes[:limit]
    return codes


def make_case(code: str, start_index: int | None = None, rng: random.Random | None = None) -> Case:
    """指定模式：给代码（和可选的起始下标）。"""
    code = str(code).zfill(6)
    df = load_bars(code)
    if len(df) < config.WARMUP_BARS + config.MIN_FUTURE:
        raise ValueError(f"{code} 只有 {len(df)} 根日线，不够开一局")
    lo = config.WARMUP_BARS
    hi = len(df) - config.MIN_FUTURE
    if start_index is None:
        start_index = (rng or random).randint(lo, hi)
    start_index = max(lo, min(int(start_index), hi))
    row = meta()
    hit = row[row["code"] == code]
    name = str(hit["name"].iloc[0]) if not hit.empty else ""
    industry = str(hit["industry"].iloc[0]) if not hit.empty else ""
    return Case(code, name, industry, start_index, len(df), df["date"].tolist())


def random_case(rng: random.Random | None = None, tries: int = 60) -> Case:
    """盲盒模式：随机一只、随机起点。抽不到够长的就换一只。"""
    rng = rng or random.Random()
    codes = tradable_codes()
    if not codes:
        raise RuntimeError(f"{config.META_FILE} 里没有可用的代码")
    last_err: Exception | None = None
    for _ in range(tries):
        code = rng.choice(codes)
        try:
            return make_case(code, None, rng)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise RuntimeError(f"抽了 {tries} 次都没抽到合适的题：{last_err}")
