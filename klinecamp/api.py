"""HTTP 接口：开一局 / 推进 / 下单 / 结算 / 历史。

会话放在内存里（一个训练营就是一个人在自己电脑上练，不需要多进程共享）。
"""

from __future__ import annotations

import random
import uuid

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from klinecamp import config, data, formula as formula_mod, formulas, indicators, layout, screener, store
from klinecamp.session import Session

app = FastAPI(title="K线训练营", version="0.1.0")

_SESSIONS: dict[str, Session] = {}
_RNG = random.Random()


class OpenIn(BaseModel):
    mode: str = "blind"          # blind / custom / screen
    code: str = ""
    condition: str = ""          # mode=screen 时用：内置条件 id，或 wb:条件名
    start_index: int | None = None
    cash: float | None = None


class OrderIn(BaseModel):
    side: str
    shares: int
    auto_next: bool = True     # 下完单直接走一根（在下一根开盘成交）


@app.get("/api/meta")
def api_meta() -> dict:
    m = data.meta()
    return {
        "ok": True,
        "data_dir": str(config.DATA_DIR),
        "universe": int(len(m)),
        "tradable": len(data.tradable_codes()),
        "config": {
            "cash": config.DEFAULT_CASH,
            "warmup_bars": config.WARMUP_BARS,
            "min_future": config.MIN_FUTURE,
            "commission_rate": config.COMMISSION_RATE,
            "min_commission": config.MIN_COMMISSION,
            "stamp_tax": config.STAMP_TAX,
        },
    }


@app.get("/api/conditions")
def api_conditions() -> dict:
    """可用的选股条件。"""
    items = [
        {"id": cid, "name": name, "hint": hint}
        for cid, (name, hint) in screener.CONDITIONS.items()
    ]
    return {"ok": True, "items": items}


@app.get("/api/conditions/{cid}/count")
def api_condition_count(cid: str) -> dict:
    """某个条件今天命中多少只（点开条件时才查）。"""
    try:
        codes = _pool(cid)
        return {"ok": True, "count": len(codes)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _pool(cid: str) -> list[str]:
    return screener.pool(cid)


@app.get("/api/layout")
def api_layout_get() -> dict:
    """界面布局（主图/副图高度、图表区宽度）。"""
    return {"ok": True, "layout": layout.load()}


@app.post("/api/layout")
def api_layout_save(patch: dict) -> dict:
    """保存布局：拖完就存，下次打开还是这个样子。"""
    try:
        return {"ok": True, "layout": layout.save(patch)}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"存不了布局：{exc}") from exc


@app.get("/api/formulas")
def api_formulas() -> dict:
    """副图公式清单：读 formulas.json（没有就用示例文件）。

    只有公开的教科书式示例在仓库里；你自己的写在 formulas.json，不进 git。
    """
    return {"ok": True, "items": formulas.load(), "default": formulas.default_id()}


class FormulaIn(BaseModel):
    name: str
    formula: str
    hint: str = ""


@app.post("/api/formulas")
def api_formula_save(req: FormulaIn) -> dict:
    """把一条公式存进 formulas.json（下次打开还在）。"""
    # 先用一段合成数据验一下语法，免得存进去一个用不了的公式
    probe = pd.DataFrame({
        "open": [10 + i * 0.1 for i in range(60)],
        "high": [10.2 + i * 0.1 for i in range(60)],
        "low": [9.8 + i * 0.1 for i in range(60)],
        "close": [10 + i * 0.1 for i in range(60)],
        "volume": [1000.0 + i for i in range(60)],
        "amount": [1e6] * 60,
    })
    try:
        formula_mod.evaluate(req.formula, probe)
    except formula_mod.FormulaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        items = formulas.save(req.name, req.formula, req.hint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "items": items, "saved_to": str(formulas.USER_FILE)}


@app.delete("/api/formulas/{name}")
def api_formula_delete(name: str) -> dict:
    """删掉一条自定义公式（只删 formulas.json 里的，示例文件不动）。"""
    try:
        items = formulas.remove(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "items": items}


@app.get("/api/session/{sid}/macd")
def api_macd(sid: str) -> dict:
    """MACD 副图（只算已可见的那几根）。"""
    sess = _get(sid)
    df = sess.visible()
    data = indicators.macd_payload([str(x) for x in df["date"]], df["close"].astype("float64"))
    return {"ok": True, **data}


@app.get("/api/session/{sid}/indicator")
def api_indicator(sid: str, formula: str = "", id: str = "") -> dict:
    """在**已可见**的 K 线上算一条副图序列（绝不碰后面的数据）。"""
    sess = _get(sid)
    text = (formula or "").strip()
    if not text and id:
        item = next((x for x in formulas.load() if x["id"] == id), None)
        if not item:
            raise HTTPException(status_code=404, detail=f"没有这个副图公式：{id}")
        text = item["formula"]
    if not text:
        raise HTTPException(status_code=400, detail="给个 formula 或 id")

    df = sess.visible()
    try:
        series = formula_mod.evaluate(text, df)
    except formula_mod.FormulaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    values = []
    for date, v in zip(df["date"].astype(str), series):
        if v != v or v is None:          # NaN 跳过，图上自然断开
            continue
        values.append({"time": date, "value": round(float(v), 4)})
    return {"ok": True, "formula": text, "values": values}


def _bars_payload(sess: Session) -> list[dict]:
    # 只发最近 400 根给前端：盲盒可能从第 1000 根开始，全画出来挤成一团没意义
    df = sess.visible().tail(config.MAX_VISIBLE_BARS)
    return [
        {
            "time": str(r["date"]),
            "open": round(float(r["open"]), 2),
            "high": round(float(r["high"]), 2),
            "low": round(float(r["low"]), 2),
            "close": round(float(r["close"]), 2),
            "volume": float(r["volume"]),
        }
        for _, r in df.iterrows()
    ]


@app.post("/api/session")
def api_open(req: OpenIn) -> dict:
    pool_n = 0
    try:
        if req.mode == "custom":
            if not req.code.strip():
                raise ValueError("指定模式要给 6 位代码")
            case = data.make_case(req.code.strip(), req.start_index, _RNG)
        elif req.mode == "screen":
            if not req.condition.strip():
                raise ValueError("条件模式要选一个条件")
            codes = _pool(req.condition.strip())
            pool_n = len(codes)
            if not codes:
                raise ValueError("这个条件今天一只都没命中，换个条件或等明天")
            # 从命中里随机抽，抽到日线不够长的就换一只
            case = None
            for code in _RNG.sample(codes, min(len(codes), 40)):
                try:
                    case = data.make_case(code, None, _RNG)
                    break
                except Exception:  # noqa: BLE001
                    continue
            if case is None:
                raise ValueError("命中的票日线都不够长，换个条件试试")
        else:
            case = data.random_case(_RNG)
    except (ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sess = Session(
        case=case,
        rows=data.load_bars(case.code),
        cash0=float(req.cash or config.DEFAULT_CASH),
    )
    sess.cash = sess.cash0
    sid = uuid.uuid4().hex[:12]
    _SESSIONS[sid] = sess
    return {
        "ok": True,
        "id": sid,
        "mode": req.mode,
        "condition": req.condition,
        "pool_size": pool_n,
        "case": case.public(reveal=req.mode == "custom"),
        "bars": _bars_payload(sess),
        "state": sess.state(),
    }


def _get(sid: str) -> Session:
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="这一局不存在（服务重启过？重开一局吧）")
    return sess


@app.get("/api/session/{sid}")
def api_state(sid: str) -> dict:
    sess = _get(sid)
    return {"ok": True, "state": sess.state(), "bars": _bars_payload(sess)}


@app.post("/api/session/{sid}/step")
def api_step(sid: str) -> dict:
    sess = _get(sid)
    try:
        state = sess.step()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "state": state, "bars": _bars_payload(sess)}


@app.post("/api/session/{sid}/order")
def api_order(sid: str, req: OrderIn) -> dict:
    """下单，然后（默认）立刻走一根——成交价就是这一根的开盘价。"""
    sess = _get(sid)
    try:
        state = sess.order(req.side, req.shares)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filled = None
    if req.auto_next:
        before = len(sess.trades)
        try:
            state = sess.step()
            if len(sess.trades) > before:
                filled = sess.trades[-1].as_dict()
        except ValueError:
            # 已经是最后一根：单挂着不动，前端会提示
            pass
    return {"ok": True, "state": state, "filled": filled,
            "bars": _bars_payload(sess) if req.auto_next else None}


@app.post("/api/session/{sid}/hold")
def api_hold(sid: str) -> dict:
    """持仓不动：撤掉未成交的单，然后走一根（等于"这一根我不操作"）。"""
    sess = _get(sid)
    sess.cancel()
    try:
        state = sess.step()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "state": state, "bars": _bars_payload(sess)}


@app.post("/api/session/{sid}/cancel")
def api_cancel(sid: str) -> dict:
    return {"ok": True, "state": _get(sid).cancel()}


@app.post("/api/session/{sid}/finish")
def api_finish(sid: str) -> dict:
    sess = _get(sid)
    result = sess.finish()
    rid = store.save(result)
    return {"ok": True, "id": rid, "result": result}


@app.get("/api/history")
def api_history(limit: int = 20) -> dict:
    return {"ok": True, "items": store.recent(limit), "summary": store.summary()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(config.WEB_DIR)), name="static")
