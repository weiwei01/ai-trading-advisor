"""抓取證交所日 K 歷史並存入本地 SQLite。

用法：
    python -m scripts.fetch_history 2330 0050 --months 3

之後即可用 scripts.run_backtest 對已存資料跑回測，回測本身不需再連網。
"""
from __future__ import annotations

import argparse

from app.db import get_connection, init_db
from app.market import repository as market_repo
from app.market.twse import fetch_history


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取台股日 K 並存入 SQLite")
    parser.add_argument("symbols", nargs="+", help="股票代號，如 2330 0050")
    parser.add_argument("--months", type=int, default=3, help="抓取最近幾個月（預設 3）")
    parser.add_argument("--delay", type=float, default=1.0, help="每次請求間隔秒數")
    args = parser.parse_args()

    conn = get_connection()
    init_db(conn)
    try:
        for symbol in args.symbols:
            print(f"抓取 {symbol} 最近 {args.months} 個月 ...", flush=True)
            candles = fetch_history(symbol, months=args.months, delay=args.delay)
            n = market_repo.save_candles(conn, symbol, candles)
            span = f"{candles[0]['date']} ~ {candles[-1]['date']}" if candles else "（無資料）"
            print(f"  {symbol}: 存入 {n} 筆 {span}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
