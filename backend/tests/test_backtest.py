"""回測引擎測試 — 隔離環境、隔日開盤成交、走實盤風控。"""
from app.advisor.base import MarketContext
from app.advisor.stub import StubAdvisor
from app.backtest import BacktestConfig, run_backtest
from app.schemas import Action, Proposal


def _make_candles(n=10, start=100.0, step=2.0):
    out = []
    for i in range(n):
        price = start + i * step
        out.append({
            "date": f"2024-06-{i + 1:02d}",
            "open": price, "high": price + 1, "low": price - 1,
            "close": price + 0.5, "volume": 1000,
        })
    return out


def test_backtest_buys_at_next_day_open():
    candles = {"2330": _make_candles()}

    def gen(ctx: MarketContext):
        # 尚未持有時買一次（回測 window 的第一個決策日）
        if not ctx.positions:
            return [Proposal(
                symbol="2330", action="buy", price=ctx.quotes.get("2330", 100.0),
                quantity=1000, confidence=0.9, reason="進場", risk_note="停損",
            )]
        return []

    result = run_backtest(
        StubAdvisor(generator=gen),
        candles,
        BacktestConfig(initial_cash=1_000_000, days=5),
    )
    assert result.equity_curve            # 有權益曲線
    assert result.final_equity > 0
    # 上漲行情買進後權益應高於起始
    assert result.total_return > 0


def test_backtest_empty_when_no_proposals():
    candles = {"2330": _make_candles()}
    result = run_backtest(
        StubAdvisor(proposals=[]), candles, BacktestConfig(days=5)
    )
    assert result.n_trades == 0
    assert result.total_return == 0.0
