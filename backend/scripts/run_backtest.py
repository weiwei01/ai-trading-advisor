"""對本地已存日 K 跑回測。

用法：
    python -m scripts.run_backtest 2330 0050 --days 20 --style 穩健波段

預設用 StubAdvisor（不燒 Token）。要用真實 Codex，設 USE_CODEX=1 與 OPENAI_API_KEY，
但回測逐日呼叫 LLM 很燒 Token（20 天約一次決策一天），請斟酌。
"""
from __future__ import annotations

import argparse

from app.backtest import BacktestConfig, run_backtest
from app.db import get_connection
from app.deps import get_advisor
from app.market import repository as market_repo
from app.schemas import SecurityType


def main() -> None:
    parser = argparse.ArgumentParser(description="對已存日 K 跑回測")
    parser.add_argument("symbols", nargs="*", help="股票代號；省略則用 DB 內全部")
    parser.add_argument("--days", type=int, default=20, help="回測天數（預設 20）")
    parser.add_argument("--cash", type=float, default=1_000_000, help="初始資金")
    parser.add_argument("--style", default="", help="策略風格描述")
    parser.add_argument("--etf", nargs="*", default=[], help="標記為 ETF 的代號（稅率不同）")
    args = parser.parse_args()

    conn = get_connection()
    try:
        symbols = args.symbols or market_repo.stored_symbols(conn)
        if not symbols:
            print("DB 內沒有任何日 K，請先執行：python -m scripts.fetch_history <代號>")
            return
        candles = market_repo.load_many(conn, symbols)
    finally:
        conn.close()

    sec_types = {s: SecurityType.ETF for s in args.etf}
    config = BacktestConfig(
        initial_cash=args.cash, days=args.days,
        strategy_style=args.style, sec_types=sec_types,
    )
    result = run_backtest(get_advisor(), candles, config)

    print(f"標的       : {', '.join(symbols)}")
    print(f"回測天數   : {args.days}")
    print(f"成交筆數   : {result.n_trades}")
    print(f"總報酬     : {result.total_return:+.2%}")
    print(f"勝率       : {result.win_rate:.1%}")
    print(f"期望值/筆  : {result.expectancy:+,.0f} 元")
    print(f"期末權益   : {result.final_equity:,.0f} 元")


if __name__ == "__main__":
    main()
