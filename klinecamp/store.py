"""训练记录（SQLite）：每局一行，用来回看「练了多少、水平有没有长」。"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from klinecamp import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS round (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  code TEXT, name TEXT, industry TEXT,
  start_date TEXT, end_date TEXT,
  bars_played INTEGER,
  return_pct REAL, max_drawdown_pct REAL, win_rate REAL,
  round_trips INTEGER, buy_hold_pct REAL, ma20_pct REAL,
  payload TEXT
);
"""


def _conn() -> sqlite3.Connection:
    path = Path(config.DB_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save(result: dict) -> int:
    conn = _conn()
    bench = result.get("benchmarks") or {}
    cur = conn.execute(
        """INSERT INTO round(created_at, code, name, industry, start_date, end_date,
                             bars_played, return_pct, max_drawdown_pct, win_rate,
                             round_trips, buy_hold_pct, ma20_pct, payload)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            result.get("code"), result.get("name"), result.get("industry"),
            result.get("start_date"), result.get("end_date"),
            result.get("bars_played"),
            result.get("return_pct"), result.get("max_drawdown_pct"),
            result.get("win_rate"), result.get("round_trips"),
            bench.get("buy_hold_pct"), bench.get("ma20_pct"),
            json.dumps(result, ensure_ascii=False),
        ),
    )
    conn.commit()
    rid = int(cur.lastrowid)
    conn.close()
    return rid


def recent(limit: int = 20) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        """SELECT id, created_at, code, name, start_date, end_date, bars_played,
                  return_pct, max_drawdown_pct, win_rate, round_trips,
                  buy_hold_pct, ma20_pct
           FROM round ORDER BY id DESC LIMIT ?""",
        (max(1, int(limit)),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def summary() -> dict:
    conn = _conn()
    row = conn.execute(
        """SELECT count(*) AS rounds,
                  avg(return_pct) AS avg_ret,
                  avg(CASE WHEN return_pct > 0 THEN 1.0 ELSE 0.0 END) * 100 AS win_rounds,
                  avg(buy_hold_pct) AS avg_hold
           FROM round"""
    ).fetchone()
    conn.close()
    out = dict(row) if row else {}
    return {
        "rounds": int(out.get("rounds") or 0),
        "avg_return_pct": round(float(out.get("avg_ret") or 0), 2),
        "win_round_pct": round(float(out.get("win_rounds") or 0), 1),
        "avg_buy_hold_pct": round(float(out.get("avg_hold") or 0), 2),
    }
