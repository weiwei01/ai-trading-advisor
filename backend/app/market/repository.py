"""日 K 的 SQLite 存取。"""
from __future__ import annotations

import sqlite3
from typing import Dict, List


def save_candles(conn: sqlite3.Connection, symbol: str, candles: List[dict]) -> int:
    """寫入日 K（同 symbol+date 以最新值覆蓋）。回傳寫入筆數。"""
    rows = [
        (symbol, c["date"], c["open"], c["high"], c["low"], c["close"], c.get("volume", 0))
        for c in candles
    ]
    conn.executemany(
        """INSERT INTO candles (symbol, date, open, high, low, close, volume)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(symbol, date) DO UPDATE SET
             open=excluded.open, high=excluded.high, low=excluded.low,
             close=excluded.close, volume=excluded.volume""",
        rows,
    )
    conn.commit()
    return len(rows)


def load_candles(conn: sqlite3.Connection, symbol: str) -> List[dict]:
    """讀取某 symbol 全部日 K（最舊到最新）。"""
    cur = conn.execute(
        "SELECT date, open, high, low, close, volume FROM candles "
        "WHERE symbol = ? ORDER BY date",
        (symbol,),
    )
    return [dict(r) for r in cur.fetchall()]


def load_many(conn: sqlite3.Connection, symbols: List[str]) -> Dict[str, List[dict]]:
    return {s: load_candles(conn, s) for s in symbols}


def stored_symbols(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")
    return [r["symbol"] for r in cur.fetchall()]
