"""验证「条件抽一局」：命中池 → 随机一只 → 开局。"""

import json
import urllib.request

BASE = "http://127.0.0.1:8760"


def post(path, body=None):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.load(r)


def main():
    for cid in ("breakout20", "pullback20", "limit_up5", "strong_lowvol"):
        n = get(f"/api/conditions/{cid}/count")["count"]
        d = post("/api/session", {"mode": "screen", "condition": cid})
        print(f"{cid:14s} 命中 {n:4d} 只 → 抽到 {d['case']['name']} 起点 {d['case']['start_date']} 池={d['pool_size']}")
        st = post(f"/api/session/{d['id']}/step")["state"]
        print(f"   走一根：{st['date']} 收盘 {st['price']} 资产 {st['equity']}")


if __name__ == "__main__":
    main()
