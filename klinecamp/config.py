r"""路径与默认参数。

行情数据不进仓库：默认读项目下的 `data/`，用环境变量指到你自己的 parquet 目录：

    KLINE_DATA_DIR=.\my-data          # 里面有 meta.parquet 和 bars/
    KLINE_DB=data\camp.sqlite3        # 训练记录（默认放在项目 data/ 下）
    KLINE_CASH=100000                 # 每局起始资金

数据格式见 docs/DATA.md。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("KLINE_DATA_DIR", ROOT / "data")).resolve()
BARS_DIR = DATA_DIR / "bars"
META_FILE = DATA_DIR / "meta.parquet"

DB_FILE = Path(os.getenv("KLINE_DB", ROOT / "data" / "camp.sqlite3"))
# 前端资源跟着包走（这样 `pip install` 之后也能找到）
WEB_DIR = Path(__file__).resolve().parent / "web"

# 交易成本（A 股常见设置，可按需改）
COMMISSION_RATE = float(os.getenv("KLINE_COMMISSION", "0.00025"))
MIN_COMMISSION = float(os.getenv("KLINE_MIN_COMMISSION", "5"))
STAMP_TAX = float(os.getenv("KLINE_STAMP_TAX", "0.001"))

DEFAULT_CASH = float(os.getenv("KLINE_CASH", "100000"))

# 一局要留够：前面 120 根（看图/指标），后面至少 60 根（够你练）
WARMUP_BARS = int(os.getenv("KLINE_WARMUP", "120"))
MIN_FUTURE = int(os.getenv("KLINE_MIN_FUTURE", "60"))

# 图表最多画多少根（盲盒可能落在第 1000 根，全画出来会挤成一团）
MAX_VISIBLE_BARS = int(os.getenv("KLINE_MAX_VISIBLE", "400"))
