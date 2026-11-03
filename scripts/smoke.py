"""接口冒烟：开一局 → 推进 → 下单 → 结算，确认整条链路通。"""

import json
import urllib.request

BASE = "http://127.0.0.1:8760"


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)


def main() -> None:
    d = post("/api/session", {"mode": "blind"})
    print("开局:", d["case"], "| 可见 K 线", len(d["bars"]))
    sid = d["id"]

    st = d["state"]
    print("初始:", st["date"], "现金", st["cash"], "价格", st["price"])

    # 买 100 股
    st = post(f"/api/session/{sid}/order", {"side": "buy", "shares": 100})["state"]
    print("挂单:", st["pending"])

    for i in range(3):
        st = post(f"/api/session/{sid}/step")["state"]
        print(f"  推进{i + 1}: {st['date']} 收盘 {st['price']} 持仓 {st['shares']} 总资产 {st['equity']}")

    # 卖 100 股
    st = post(f"/api/session/{sid}/order", {"side": "sell", "shares": 100})["state"]
    print("挂卖单:", st["pending"])
    st = post(f"/api/session/{sid}/step")["state"]
    print("卖出后: 持仓", st["shares"], "现金", st["cash"])

    # 走到最后
    while True:
        st = post(f"/api/session/{sid}/step")["state"]
        if st["bars_left"] <= 0:
            break
    r = post(f"/api/session/{sid}/finish")
    res = r["result"]
    print("结算:", res["name"], res["code"], "收益", res["return_pct"], "%")
    print("  基准: 买入持有", res["benchmarks"]["buy_hold_pct"], "% | MA20", res["benchmarks"]["ma20_pct"], "%")
    print("  交易", len(res["trades"]), "笔, 胜率", res["win_rate"], ", 回撤", res["max_drawdown_pct"], "%")
    print("历史:", get("/api/history?limit=3")["summary"])


if __name__ == "__main__":
    main()
