"""規則型 advisor 測試 — 訊號判定為純函式，可確定性驗證。"""
from app.advisor.rules import RuleConfig, evaluate_symbol, sma
from app.schemas import Action


def _candles(closes):
    return [
        {"date": f"2024-06-{i + 1:02d}", "open": c, "high": c + 1,
         "low": c - 1, "close": c, "volume": 1000}
        for i, c in enumerate(closes)
    ]


def test_sma_basic_and_insufficient():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 5) is None


def test_golden_cross_triggers_buy():
    # 先跌後急漲，製造短均線上穿長均線
    closes = [100] * 20 + [101, 103, 106, 110, 115]
    p = evaluate_symbol("2330", _candles(closes), held=0, cfg=RuleConfig())
    assert p is not None
    assert p.action == Action.BUY
    assert p.confidence > 0
    assert p.reason and p.risk_note


def test_no_signal_returns_none_when_flat():
    closes = [100] * 30
    assert evaluate_symbol("2330", _candles(closes), held=0, cfg=RuleConfig()) is None


def test_death_cross_triggers_sell_when_held():
    closes = [100] * 20 + [99, 96, 92, 88, 84]
    p = evaluate_symbol("2330", _candles(closes), held=1000, cfg=RuleConfig())
    assert p is not None
    assert p.action == Action.SELL
    assert p.quantity <= 1000


def test_no_buy_when_already_holding():
    closes = [100] * 20 + [101, 103, 106, 110, 115]
    # 已持有時不應再產生買進訊號
    p = evaluate_symbol("2330", _candles(closes), held=1000, cfg=RuleConfig())
    assert p is None or p.action != Action.BUY
