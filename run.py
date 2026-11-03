"""启动：python run.py  → http://127.0.0.1:8760

真正的逻辑在 `klinecamp/cli.py`；这个文件只是让人双击 / `python run.py` 都有入口。
装了包之后也可以直接用 `kline-camp` 命令。
"""

from __future__ import annotations

from klinecamp.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
