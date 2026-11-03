"""生成 README 用的三张截图（跑在 demo 数据上，画面里没有任何真实票）。

用法：
    python scripts/make_demo_data.py --out .\\demo-data
    set KLINE_DATA_DIR=.\\demo-data
    python run.py                      # 另开一个窗口
    python scripts/make_shots.py
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

# 浏览器路径：默认用 Edge，换了浏览器就设 EDGE_PATH（或 CHROME_PATH）
EDGE = os.getenv("EDGE_PATH") or os.getenv("CHROME_PATH") or (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
PORT = 9365
OUT = Path("docs/shots")
URL = "http://127.0.0.1:8760/"
WIDTH = 1400          # CSS 宽
SCALE = 2             # 2 倍像素：GitHub 会缩到 ~880px 显示，2x 缩下去才清楚


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prof = tempfile.mkdtemp(prefix="edge-shot-")
    p = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={prof}", f"--window-size={WIDTH},1200", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        url = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    for x in json.load(r):
                        if x.get("type") == "page":
                            url = x["webSocketDebuggerUrl"]
            except Exception:  # noqa: BLE001
                time.sleep(0.4)
            if url:
                break
        ws = websocket.create_connection(url, timeout=60)
        seq = [0]

        def call(m, **kw):
            seq[0] += 1
            ws.send(json.dumps({"id": seq[0], "method": m, "params": kw}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == seq[0]:
                    return msg.get("result")

        def js(e):
            r = call("Runtime.evaluate", expression=e, returnByValue=True, awaitPromise=True)
            if r.get("exceptionDetails"):
                return "ERR " + str(r["exceptionDetails"].get("text"))
            return r.get("result", {}).get("value")

        def content_height() -> int:
            return int(js("""(() => {
                const panes = [...document.querySelectorAll('.pane')];
                const bottom = Math.max(
                  panes.length ? panes[panes.length - 1].getBoundingClientRect().bottom : 0,
                  document.querySelector('.side').getBoundingClientRect().bottom);
                return Math.ceil(bottom + 24);
            })()"""))

        def shot(name: str, height: int | None = None) -> None:
            """把视口高度改成内容高度再截，保证画面里没有大片空白。"""
            h = height or content_height()
            call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=h,
                 deviceScaleFactor=SCALE, mobile=False)
            time.sleep(0.6)
            img = call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
            (OUT / name).write_bytes(base64.b64decode(img["data"]))
            print(f"saved {OUT / name}  ({WIDTH}x{h} css @{SCALE}x)")

        call("Page.enable")
        call("Runtime.enable")
        call("Page.navigate", url=URL)
        time.sleep(5)
        js("document.getElementById('btnBlind').click()")
        time.sleep(3)
        # 先买 100 股（点买入会自动走一根），让截图里有持仓、结算里有成交
        js("document.getElementById('btnBuy').click()")
        time.sleep(1.5)
        for _ in range(2):
            js("document.getElementById('btnHold').click()")
            time.sleep(0.4)

        # 加一个公式副图（已经是勾着的就跳过，避免又点掉）
        js("document.getElementById('btnFormulaMgr').click()")
        time.sleep(1.5)
        js("""(() => {
            const boxes = [...document.querySelectorAll('#fmShow input')];
            if (boxes.some((b) => b.checked)) return 'already';
            const t = boxes[1] || boxes[0];
            if (t) t.click();
            return t ? t.value : 'none';
        })()""")
        time.sleep(2)
        js("document.getElementById('fmClose').click()")
        time.sleep(1)
        shot("panels.png")

        # 十字光标贯通：真实鼠标事件
        box = js("(() => { const r = document.querySelector('#chart').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        call("Input.dispatchMouseEvent", type="mouseMoved",
             x=box[0] + box[2] * 0.62, y=box[1] + box[3] * 0.45, button="none")
        time.sleep(1.2)
        shot("crosshair.png")

        # 结算：先卖掉、再走两根，让结果里有成交和盈亏
        js("document.getElementById('btnSell').click()")
        time.sleep(1.5)
        for _ in range(2):
            js("document.getElementById('btnHold').click()")
            time.sleep(0.4)
        js("document.getElementById('btnFinish').click()")
        time.sleep(2.5)
        m = js("(() => { const r = document.querySelector('#resultModal .modal-body').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        img = call("Page.captureScreenshot", format="png", clip={
            "x": m[0] - 6, "y": m[1] - 6, "width": m[2] + 12, "height": m[3] + 12, "scale": 1,
        }, captureBeyondViewport=False)
        (OUT / "settle.png").write_bytes(base64.b64decode(img["data"]))
        print(f"saved {OUT / 'settle.png'}")
        return 0
    finally:
        p.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
