from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app import config

DEFAULT_DB = Path(config.DB_PATH)

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT NOT NULL,
    risk_note TEXT NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    decision TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS candle_fetch_failures (
    symbol TEXT NOT NULL,
    yyyymm TEXT NOT NULL,
    error TEXT NOT NULL,
    failed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (symbol, yyyymm)
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    sec_type TEXT NOT NULL DEFAULT 'stock',
    proposal_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_metadata (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market_type TEXT NOT NULL,
    sec_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backtest_cache (
    context_hash TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Initial standard symbols list to populate security_metadata
INITIAL_SECURITIES = [
    # TSE (上市) - Stocks
    ("2330", "台積電", "tse", "stock"),
    ("2317", "鴻海", "tse", "stock"),
    ("2454", "聯發科", "tse", "stock"),
    ("2308", "台達電", "tse", "stock"),
    ("2382", "廣達", "tse", "stock"),
    ("2881", "富邦金", "tse", "stock"),
    ("2882", "國泰金", "tse", "stock"),
    ("2603", "長榮", "tse", "stock"),
    # OTC (上櫃) - Stocks
    ("5483", "中美晶", "otc", "stock"),
    ("6488", "環球晶", "otc", "stock"),
    ("5347", "世界", "otc", "stock"),
    # ETFs (TSE)
    ("0050", "元大台灣50", "tse", "etf"),
    ("0056", "元大高股息", "tse", "etf"),
    ("00878", "國泰永續高股息", "tse", "etf"),
]


def get_connection(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Populate default securities
    conn.executemany(
        """INSERT OR IGNORE INTO security_metadata (symbol, name, market_type, sec_type)
           VALUES (?, ?, ?, ?)""",
        INITIAL_SECURITIES,
    )
    conn.commit()


@contextmanager
def temp_db() -> Iterator[sqlite3.Connection]:
    """回測用：完全隔離的記憶體資料庫，結束即丟棄。"""
    conn = get_connection(":memory:")
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()

