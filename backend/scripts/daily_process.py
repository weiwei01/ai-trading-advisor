"""每日盤後流程腳本：抓取今日日 K -> LLM 產生交易提案 -> 風控檢驗 -> 儲存至待裁決提案表。

用法：
    python -m scripts.daily_process [--date YYYY-MM-DD] [--strategy "穩健波段"]
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import time

from app import config
from app.advisor.base import MarketContext
from app.db import get_connection, init_db
from app.deps import get_advisor, get_quote_source
from app.pnl import brokerage_fee, transaction_tax
from app.repository import (
    get_security_metadata,
    list_fills,
    list_securities,
    save_proposal,
)
from app.risk import RiskConfig, RiskEngine
from app.market import repository as market_repo
from app.market.twse import fetch_daily_candles


def get_current_portfolio(conn, initial_cash: float = 1_000_000.0) -> tuple[float, dict[str, int]]:
    """從成交紀錄 (fills) 計算當前可用的現金與部位持股。"""
    fills = list_fills(conn)
    cash = initial_cash
    positions: dict[str, int] = {}
    
    # fills 預設是最新到最舊排序，因此需反向處理
    for f in reversed(fills):
        qty = f["quantity"]
        price = f["price"]
        side = f["side"]
        sec_type = f["sec_type"]
        gross = price * qty
        fee = brokerage_fee(gross)
        
        if side == "buy":
            cost = gross + fee
            cash -= cost
            positions[f["symbol"]] = positions.get(f["symbol"], 0) + qty
        elif side == "sell":
            tax = transaction_tax(gross, sec_type)
            proceeds = gross - fee - tax
            cash += proceeds
            positions[f["symbol"]] = positions.get(f["symbol"], 0) - qty
            if positions[f["symbol"]] <= 0:
                positions.pop(f["symbol"], None)
                
    return cash, positions


def main() -> None:
    parser = argparse.ArgumentParser(description="每日盤後分析流程")
    parser.add_argument("--date", help="指定決策基準日期，格式 YYYY-MM-DD，預設為今日")
    parser.add_argument("--strategy", default="穩健中性", help="策略風格，例如 '穩健波段', '積極動能'")
    args = parser.parse_args()

    # 基準日期
    if args.date:
        as_of = args.date
    else:
        as_of = date.today().strftime("%Y-%m-%d")

    conn = get_connection()
    init_db(conn)
    try:
        securities = list_securities(conn)
        if not securities:
            print("security_metadata 主檔表為空，無法執行。")
            return

        symbols = [s["symbol"] for s in securities]
        print(f"基準決策日: {as_of}")
        print(f"追蹤標的: {', '.join(symbols)}")

        # 1. 抓取當月最新日 K 以更新資料庫
        yyyymm = as_of.replace("-", "")[:6] + "01"
        print(f"\n正在抓取 {yyyymm[:4]}年{yyyymm[4:6]}月 最新成交數據 ...")
        for s in symbols:
            try:
                candles = fetch_daily_candles(s, yyyymm)
                if candles:
                    n = market_repo.save_candles(conn, s, candles)
                    print(f"  {s}: 寫入/更新 {n} 筆 K 棒數據")
                else:
                    print(f"  {s}: 月度資料尚未公布或無資料")
            except Exception as e:
                print(f"  {s}: 抓取失敗: {e}")
            time.sleep(1.0)  # 防禦流量限制

        # 2. 獲取即時/收盤報價
        print("\n取得最新報價與帳戶部位 ...")
        q_source = get_quote_source()
        quotes = q_source.get_quotes(symbols)
        
        # 如果報價源沒有提供報價，則使用最新一天的收盤價作為報價
        for s in symbols:
            if s not in quotes or quotes[s] <= 0:
                s_candles = market_repo.load_candles(conn, s)
                if s_candles:
                    quotes[s] = s_candles[-1]["close"]
                else:
                    quotes[s] = 0.0

        # 計算當前可用現金與部位
        cash, positions = get_current_portfolio(conn)
        equity = cash + sum(positions.get(s, 0) * quotes.get(s, 0.0) for s in positions)
        print(f"  帳戶可用現金: {cash:,.0f} 元")
        print(f"  當前持股部位: {positions}")
        print(f"  帳戶總權益市值: {equity:,.0f} 元")

        # 3. 準備 MarketContext
        candles_context = {}
        for s in symbols:
            s_candles = market_repo.load_candles(conn, s)
            # 只餵到 as_of 當天為止的歷史
            candles_context[s] = [c for c in s_candles if c["date"] <= as_of]

        ctx = MarketContext(
            as_of=as_of,
            candles=candles_context,
            quotes=quotes,
            positions=positions,
            cash=cash,
            strategy_style=args.strategy,
        )

        # 4. 呼叫 LLM 顧問產生提案
        print(f"\n正在向 AI 交易顧問 ({config.CODEX_MODEL}) 請求分析與提案 ...")
        advisor = get_advisor()
        batch = advisor.propose(ctx)

        print(f"AI 顧問回傳 {len(batch.proposals)} 個提案。進行風控評估 ...")

        # 5. 風控引擎審核並入庫
        risk_engine = RiskEngine(RiskConfig(
            max_position_pct=config.MAX_POSITION_PCT,
            max_order_value=config.MAX_ORDER_VALUE,
            min_confidence=config.MIN_CONFIDENCE,
            allow_short=config.ALLOW_SHORT,
        ))

        saved_count = 0
        blocked_count = 0

        for p in batch.proposals:
            sec_meta = get_security_metadata(conn, p.symbol)
            sec_type = sec_meta["sec_type"] if sec_meta else "stock"
            
            result = risk_engine.evaluate(
                p,
                cash=cash,
                total_equity=equity,
                positions=positions,
                sec_type=sec_type,
            )
            
            if result.approved:
                # 寫入 proposals 提案表，預設狀態為 pending
                proposal_id = save_proposal(conn, p)
                print(f"  ✅ 提案已儲存 (ID: {proposal_id}) -> {p.symbol} {p.action.value.upper()} {p.quantity} 股 @ {p.price:.2f} (理由: {p.reason})")
                saved_count += 1
            else:
                print(f"  ❌ 提案未通過風控被阻擋 -> {p.symbol} {p.action.value.upper()} {p.quantity} 股 @ {p.price:.2f}")
                for reason in result.reasons:
                    print(f"    原因: {reason}")
                blocked_count += 1

        print(f"\n流程結束：成功入庫 {saved_count} 筆，阻擋 {blocked_count} 筆。")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
