"""命令行入口：`kline-camp` 或 `python -m klinecamp`。

处理三件容易被卡住的事：
  1. 依赖没装 → 直接告诉你敲哪条命令（不甩 traceback）
  2. 端口被上一次没关的实例占着 → 认出它并告诉你 URL，而不是丢一个 10048
  3. 端口被别的程序占着 → 自动往后找一个空端口
"""

from __future__ import annotations

import os
import socket
import sys
import urllib.request

HOST = os.getenv("KLINE_HOST", "127.0.0.1")
PORT = int(os.getenv("KLINE_PORT", "8760"))


def say(*args: object) -> None:
    """总是立刻刷出去：被重定向或管道接走时，缓冲会让提示看不到。"""
    print(*args, flush=True)


def _missing() -> list[str]:
    import importlib.util as u

    need = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pandas": "pandas",
        "pyarrow": "pyarrow",
    }
    return [pkg for mod, pkg in need.items() if not u.find_spec(mod)]


def _free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((HOST, port)) != 0


def _is_ours(port: int) -> bool:
    """端口上跑的是不是这个训练营（而不是别的程序）。"""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/meta", timeout=2) as r:
            return r.status == 200 and b'"ok"' in r.read(200)
    except Exception:  # noqa: BLE001
        return False


def _open(url: str) -> None:
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    missing = _missing()
    if missing:
        say("还差这些依赖：" + "、".join(missing))
        say()
        say("装一下（二选一）：")
        say("   python -m pip install -r requirements.txt")
        say("   python -m pip install " + " ".join(missing))
        say()
        say(f"你在用的 Python：{sys.executable}")
        say("这台机器上有多个 Python 的话，用 `py -0` 看看都有哪些版本。")
        return 1

    port = PORT
    if not _free(port):
        if _is_ours(port):
            url = f"http://{HOST}:{port}"
            say("")
            say("  ============================================================")
            say("    训练营已经在运行了 —— 一次只能跑一个")
            say("  ============================================================")
            say("")
            say(f"    正在使用： {url}")
            say("")
            say("    你这个黑窗口是第二次启动，不会再起一个。")
            say("    之前那个窗口可能被别的窗口挡住了，找一下。")
            say("")
            say("    想继续用 → 浏览器已经帮你打开了，直接用就行")
            say("    想重开   → 先关掉之前那个黑窗口（或在里面按 Ctrl+C），")
            say("               再重新启动")
            say("")
            say("  ============================================================")
            _open(url)
            return 0
        for cand in range(PORT + 1, PORT + 20):
            if _free(cand):
                port = cand
                break
        else:
            say(f"端口 {PORT}~{PORT + 19} 都占着，先用 KLINE_PORT 指定一个别的端口。")
            return 1
        say(f"端口 {PORT} 被别的程序占着，改用 {port}")

    import uvicorn

    from klinecamp import config

    say(f"K线训练营： http://{HOST}:{port}")
    say(f"数据目录： {config.DATA_DIR}")
    if not config.META_FILE.exists():
        say("（这个目录里还没有 meta.parquet —— 先按 docs/DATA.md 放数据，")
        say("  或者跑 python scripts/make_demo_data.py 造一份虚构行情试试）")
    say("（这个窗口别关，关了服务就停了）")
    uvicorn.run("klinecamp.api:app", host=HOST, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
