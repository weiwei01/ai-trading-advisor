"""損益計算測試 — FIFO 配對與費用扣除。"""
from app.pnl import (
    Fill,
    brokerage_fee,
    compute_pnl,
    transaction_tax,
    MIN_BROKERAGE,
)
from app.schemas import SecurityType


def test_min_brokerage_floor():
    # 小額交易套用單筆最低手續費
    assert brokerage_fee(1000) == MIN_BROKERAGE


def test_etf_vs_stock_tax_differ():
    amount = 100_000
    assert transaction_tax(amount, SecurityType.STOCK) == 300.0
    assert transaction_tax(amount, SecurityType.ETF) == 100.0


def test_fifo_realized_pnl_with_fees():
    fills = [
        Fill("2330", "buy", 100.0, 1000),    # 成本 100,000 + 手續費
        Fill("2330", "buy", 110.0, 1000),
        Fill("2330", "sell", 120.0, 1000),   # 應配到第一批 100 元
    ]
    report = compute_pnl(fills, market_prices={"2330": 130.0})

    assert len(report.realized) == 1
    trade = report.realized[0]
    assert trade.buy_price == 100.0
    assert trade.sell_price == 120.0
    # 毛利 20,000，扣掉買賣手續費與證交稅後應小於 20,000 但為正
    assert 0 < trade.pnl < 20_000

    # 剩一批 110 元未實現，市價 130
    assert len(report.positions) == 1
    pos = report.positions[0]
    assert pos.quantity == 1000
    assert pos.unrealized_pnl > 0


def test_oversell_raises():
    fills = [Fill("2330", "buy", 100.0, 100), Fill("2330", "sell", 110.0, 200)]
    try:
        compute_pnl(fills, {})
    except ValueError as e:
        assert "超過持有" in str(e)
    else:
        raise AssertionError("應該對超賣丟出 ValueError")
