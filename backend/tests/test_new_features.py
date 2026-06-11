"""測試新加入的模組與功能，包含上櫃抓取、風控擴充、填單 endpoints 與 token 統計。"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.db import get_connection, init_db
from app.market.tpex import fetch_otc_daily_candles
from app.advisor.rules import RuleConfig, get_raw_signal, get_confirmed_signal, evaluate_symbol
from app import repository
from app.schemas import Proposal, Action


def test_tpex_otc_candles_fetching_and_parsing():
    mock_payload = {
        "stat": "ok",
        "tables": [{
            "data": [
                ["112/08/01", "1,000", "50,000,000", "50.0", "51.5", "49.5", "51.0", "1.0", "100"],
                ["112/08/02", "2,000", "102,000,000", "51.0", "52.0", "50.5", "51.5", "0.5", "200"],
            ]
        }]
    }
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp
        
        candles = fetch_otc_daily_candles("5483", "20230801")
        
        assert len(candles) == 2
        assert candles[0]["date"] == "2023-08-01"
        assert candles[0]["open"] == 50.0
        assert candles[0]["high"] == 51.5
        assert candles[0]["low"] == 49.5
        assert candles[0]["close"] == 51.0
        assert candles[0]["volume"] == 1000000.0


def test_whipsaw_confirmation_filter():
    # 建立一串模擬的 K 線
    candles = [{"date": f"2023-01-{i:02d}", "close": float(100 + i)} for i in range(1, 35)]
    
    cfg_no_confirm = RuleConfig(short_window=5, long_window=20, confirm_days=1)
    cfg_confirm_2 = RuleConfig(short_window=5, long_window=20, confirm_days=2)
    
    # 測試原始訊號與確認訊號
    idx = len(candles) - 1
    # 我們這裡手動模擬 get_raw_signal 被 Mock
    with patch("app.advisor.rules.get_raw_signal") as mock_raw:
        # 在 idx 處為 buy，在 idx-1 處不是 buy
        mock_raw.side_effect = lambda i, *args: "buy" if i == idx else None
        
        assert get_confirmed_signal(idx, candles, cfg_no_confirm) == "buy"
        # 由於需要確認兩天，而前一天非 buy，因此應回傳 None
        assert get_confirmed_signal(idx, candles, cfg_confirm_2) is None

        # 如果前兩天都是 buy
        mock_raw.side_effect = lambda i, *args: "buy" if i in (idx, idx - 1) else None
        assert get_confirmed_signal(idx, candles, cfg_confirm_2) == "buy"


def test_whipsaw_min_holding_days_filter():
    candles = [{"date": f"2023-01-{i:02d}", "close": float(100 + i)} for i in range(1, 30)]
    
    cfg = RuleConfig(short_window=5, long_window=20, min_holding_days=3)
    
    with patch("app.advisor.rules.get_confirmed_signal") as mock_conf:
        # 目前 (idx = 28) 觸發了 sell 訊號。上一個 buy 訊號在 idx = 27 (持有 1 天)
        mock_conf.side_effect = lambda i, *args: "sell" if i == 28 else ("buy" if i == 27 else None)
        
        proposal = evaluate_symbol("2330", candles, held=1000, cfg=cfg)
        # 由於持有天數為 1天 < 最短限制 3 天，因此應過濾掉，回傳 None
        assert proposal is None

        # 若上一個 buy 在 idx = 24 (持有 4 天)
        mock_conf.side_effect = lambda i, *args: "sell" if i == 28 else ("buy" if i == 24 else None)
        proposal = evaluate_symbol("2330", candles, held=1000, cfg=cfg)
        assert proposal is not None
        assert proposal.action == Action.SELL


def test_token_usage_and_backtest_cache_repository_functions():
    conn = get_connection(":memory:")
    init_db(conn)
    try:
        # 測試 token usage
        repository.log_token_usage(conn, "gpt-4o-mini", 100, 50)
        repository.log_token_usage(conn, "gpt-4o-mini", 120, 60)
        
        usage = repository.get_total_token_usage(conn)
        assert usage["calls"] == 2
        assert usage["prompt_tokens"] == 220
        assert usage["completion_tokens"] == 110

        # 測試 backtest cache
        ctx_hash = "abc123hash"
        assert repository.get_backtest_cache(conn, ctx_hash) is None
        
        repository.save_backtest_cache(conn, ctx_hash, '{"status": "ok"}')
        assert repository.get_backtest_cache(conn, ctx_hash) == '{"status": "ok"}'
    finally:
        conn.close()


def test_fills_manual_trades_management():
    conn = get_connection(":memory:")
    init_db(conn)
    try:
        fill_id = repository.save_fill(
            conn, symbol="2330", side="buy", price=100.0, quantity=1000, sec_type="stock"
        )
        assert fill_id > 0
        
        fills = repository.list_fills(conn)
        assert len(fills) == 1
        assert fills[0]["symbol"] == "2330"
        assert fills[0]["side"] == "buy"
        assert fills[0]["price"] == 100.0
        assert fills[0]["quantity"] == 1000
    finally:
        conn.close()
