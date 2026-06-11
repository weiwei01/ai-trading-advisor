"""抓取證交所日 K 歷史並存入本地 SQLite。

用法：
    python -m scripts.fetch_history 2330 0050 --months 3
    python -m scripts.fetch_history 2330 0050 --from 2023-01 --to 2025-12

之後即可用 scripts.run_backtest 對已存資料跑回測，回測本身不需再連網。
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict

from app.db import get_connection, init_db
from app.market import repository as market_repo
from app.market.twse import fetch_daily_candles, month_range, recent_months


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取台股日 K 並存入 SQLite")
    parser.add_argument("symbols", nargs="+", help="股票代號，如 2330 0050")
    parser.add_argument("--months", type=int, default=3, help="抓取最近幾個月（預設 3）")
    parser.add_argument("--from", dest="from_month", help="起始月份，如 2023-01")
    parser.add_argument("--to", dest="to_month", help="結束月份，如 2025-12；預設本月")
    parser.add_argument("--delay", type=float, default=1.0, help="每次請求間隔秒數")
    parser.add_argument("--force", action="store_true", help="即使該月已有資料也重新抓取")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="只重試先前記錄為失敗的 symbol/月，不用重跑整批",
    )
    args = parser.parse_args()

    conn = get_connection()
    init_db(conn)
    try:
        batches = _build_batches(conn, args)
        if not batches:
            print("沒有需要抓取的月份。")
            return

        for symbol, months in batches.items():
            print(f"抓取 {symbol}: {len(months)} 個月份 ...", flush=True)
            total = 0
            for yyyymm in months:
                label = f"{yyyymm[:4]}-{yyyymm[4:6]}"
                if (
                    not args.force
                    and not args.retry_failed
                    and market_repo.has_month_data(conn, symbol, yyyymm)
                ):
                    print(f"  {label}: 已有資料，略過")
                    continue

                try:
                    candles = fetch_daily_candles(symbol, yyyymm)
                except Exception as exc:  # noqa: BLE001 - CLI 要記錄外部 API 的各種失敗並續跑
                    market_repo.record_fetch_failure(conn, symbol, yyyymm, str(exc))
                    print(f"  {label}: 失敗，已記錄：{exc}")
                else:
                    n = market_repo.save_candles(conn, symbol, candles)
                    market_repo.clear_fetch_failure(conn, symbol, yyyymm)
                    total += n
                    span = (
                        f"{candles[0]['date']} ~ {candles[-1]['date']}"
                        if candles
                        else "無資料"
                    )
                    print(f"  {label}: 存入 {n} 筆 {span}")
                time.sleep(args.delay)
            print(f"  {symbol}: 本次共寫入/更新 {total} 筆")
    finally:
        conn.close()


def _build_batches(conn, args) -> dict[str, list[str]]:
    if args.retry_failed:
        failures = market_repo.list_fetch_failures(conn, args.symbols)
        batches: dict[str, list[str]] = defaultdict(list)
        for row in failures:
            batches[row["symbol"]].append(row["yyyymm"])
        return dict(batches)

    months = month_range(args.from_month, args.to_month) if args.from_month else recent_months(args.months)
    return {symbol: months for symbol in args.symbols}


if __name__ == "__main__":
    main()
