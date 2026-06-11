"""參數掃描與策略驗證腳本。

用法：
    python -m scripts.scan_params
"""
from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
from typing import Dict, List

from app.advisor.rules import RuleBasedAdvisor, RuleConfig
from app.backtest import BacktestConfig, run_backtest
from app.db import get_connection
from app.market import repository as market_repo


def main() -> None:
    conn = get_connection()
    try:
        symbols = market_repo.stored_symbols(conn)
        if not symbols:
            print("資料庫內沒有 K 棒資料，請先執行 fetch_history 抓取。")
            return

        print(f"讀取 {len(symbols)} 檔標的資料 ...")
        all_candles = market_repo.load_many(conn, symbols)
        
        # 1. 取得所有交易日並切分 In-Sample (IS, 70%) 與 Out-of-Sample (OOS, 30%)
        all_dates = sorted(list({c["date"] for s in all_candles for c in all_candles[s]}))
        if len(all_dates) < 20:
            print("交易日數量不足（需至少 20 天以上），無法做 IS/OOS 切分。")
            return

        split_idx = int(len(all_dates) * 0.7)
        is_dates = all_dates[:split_idx]
        oos_dates = all_dates[split_idx:]
        
        print(f"歷史交易日總數: {len(all_dates)}")
        print(f"  In-Sample 區間: {is_dates[0]} ~ {is_dates[-1]} ({len(is_dates)} 天)")
        print(f"  Out-of-Sample 區間: {oos_dates[0]} ~ {oos_dates[-1]} ({len(oos_dates)} 天)")

        # 準備 IS 與 OOS 的 candles dict
        is_candles = {
            s: [c for c in cs if c["date"] in is_dates]
            for s, cs in all_candles.items()
        }
        oos_candles = {
            s: [c for c in cs if c["date"] in oos_dates]
            for s, cs in all_candles.items()
        }

        # 2. 定義 Grid 參數範圍
        short_windows = [3, 5, 8]
        long_windows = [15, 20, 30]
        breakout_windows = [10, 20]
        confirm_days_list = [1, 2]
        min_holding_days_list = [0, 3]

        grid = list(itertools.product(
            short_windows,
            long_windows,
            breakout_windows,
            confirm_days_list,
            min_holding_days_list
        ))

        print(f"\n開始對 {len(grid)} 組參數進行 In-Sample 掃描 ...")

        best_params = None
        best_is_return = -float("inf")
        best_is_result = None
        
        results_summary = []

        for short, long, breakout, confirm, min_hold in grid:
            if short >= long:
                continue
            
            cfg = RuleConfig(
                short_window=short,
                long_window=long,
                breakout_window=breakout,
                confirm_days=confirm,
                min_holding_days=min_hold,
                position_size=1000,
            )
            advisor = RuleBasedAdvisor(cfg)
            bt_cfg = BacktestConfig(
                initial_cash=1_000_000,
                days=len(is_dates) - 1,
            )
            
            # 跑 IS 回測
            res = run_backtest(advisor, is_candles, bt_cfg)
            
            param_key = f"S{short}_L{long}_B{breakout}_C{confirm}_H{min_hold}"
            results_summary.append({
                "params": param_key,
                "cfg": {
                    "short_window": short,
                    "long_window": long,
                    "breakout_window": breakout,
                    "confirm_days": confirm,
                    "min_holding_days": min_hold
                },
                "is_return": res.total_return,
                "is_win_rate": res.win_rate,
                "is_expectancy": res.expectancy,
                "is_trades": res.n_trades,
                "is_mdd": res.max_drawdown,
            })

            # 用 IS 的總報酬挑出最佳參數
            if res.total_return > best_is_return:
                best_is_return = res.total_return
                best_params = cfg
                best_is_result = res

        print("In-Sample 掃描完成。")
        if not best_params:
            print("無法挑出有效參數。")
            return

        bp_dict = {
            "short_window": best_params.short_window,
            "long_window": best_params.long_window,
            "breakout_window": best_params.breakout_window,
            "confirm_days": best_params.confirm_days,
            "min_holding_days": best_params.min_holding_days,
        }
        print(f"\n🏆 In-Sample 最佳參數組: {bp_dict}")
        print(f"  報酬率: {best_is_result.total_return*100:.2f}% | 勝率: {best_is_result.win_rate*100:.1f}% | 交易次數: {best_is_result.n_trades} | MDD: {best_is_result.max_drawdown*100:.2f}%")

        # 3. 對最佳參數跑 Out-of-Sample 驗證
        print("\n開始進行 Out-of-Sample 驗證 ...")
        oos_advisor = RuleBasedAdvisor(best_params)
        oos_bt_cfg = BacktestConfig(
            initial_cash=1_000_000,
            days=len(oos_dates) - 1,
        )
        oos_res = run_backtest(oos_advisor, oos_candles, oos_bt_cfg)

        print("OOS 驗證完成。")
        print(f"📊 Out-of-Sample 表現:")
        print(f"  報酬率: {oos_res.total_return*100:.2f}%")
        print(f"  勝率: {oos_res.win_rate*100:.1f}%")
        print(f"  交易次數: {oos_res.n_trades}")
        print(f"  MDD: {oos_res.max_drawdown*100:.2f}%")
        print(f"  Sharpe: {oos_res.sharpe_ratio:.2f}")

        # 4. 輸出 Markdown 報告
        report_path = Path(conn.execute("PRAGMA database_list").fetchone()["file"]).parent / "scan_report.md"
        if report_path.name == "":
            report_path = Path(__file__).resolve().parent.parent / "data" / "scan_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 排序所有掃描參數以列出前 5 名
        top_results = sorted(results_summary, key=lambda x: x["is_return"], reverse=True)[:5]
        
        md_content = f"""# 參數掃描與策略驗證報告

## 1. 區間設定
- **In-Sample (訓練集) 區間**: {is_dates[0]} ~ {is_dates[-1]} ({len(is_dates)} 天)
- **Out-of-Sample (測試集) 區間**: {oos_dates[0]} ~ {oos_dates[-1]} ({len(oos_dates)} 天)
- **測試標的**: {", ".join(symbols)}

## 2. 最佳參數與對照表現
最佳參數組: `S{best_params.short_window}_L{best_params.long_window}_B{best_params.breakout_window}_C{best_params.confirm_days}_H{best_params.min_holding_days}`

| 評估指標 | In-Sample (訓練期) | Out-of-Sample (驗證期) |
| :--- | :--- | :--- |
| **總報酬率** | {best_is_result.total_return*100:.2f}% | {oos_res.total_return*100:.2f}% |
| **勝率** | {best_is_result.win_rate*100:.1f}% | {oos_res.win_rate*100:.1f}% |
| **成交筆數** | {best_is_result.n_trades} | {oos_res.n_trades} |
| **最大回撤 (MDD)** | {best_is_result.max_drawdown*100:.2f}% | {oos_res.max_drawdown*100:.2f}% |
| **Sharpe Ratio** | {best_is_result.sharpe_ratio:.2f} | {oos_res.sharpe_ratio:.2f} |
| **交易成本佔獲利比** | {best_is_result.tx_cost_ratio*100:.2f}% | {oos_res.tx_cost_ratio*100:.2f}% |

## 3. In-Sample 排名前 5 的參數組
| 參數名稱 | 總報酬率 | 勝率 | 交易次數 | MDD |
| :--- | :---: | :---: | :---: | :---: |
"""
        for r in top_results:
            md_content += f"| `{r['params']}` | {r['is_return']*100:.2f}% | {r['is_win_rate']*100:.1f}% | {r['is_trades']} | {r['is_mdd']*100:.2f}% |\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"\n報告已成功儲存至: {report_path.resolve()}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
