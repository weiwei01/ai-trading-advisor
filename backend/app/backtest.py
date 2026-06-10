"""回測引擎 — 目前最燒 Token 的功能。

機制：
- 用第 d 天做決策時，只餵到第 d 天為止的 K 棒（避免未來資訊洩漏）。
- 成交價用「隔一個交易日的開盤價」計算。
- 跑在隔離的暫存資料庫，走與實盤相同的風控引擎，手續費與稅照算。
輸出：權益曲線、總報酬、勝率、期望值，先確認打法是否真有正期望值。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.advisor.base import MarketContext, TradingAdvisor
from app.pnl import Fill, compute_pnl
from app.risk import RiskConfig, RiskEngine
from app.schemas import Action, SecurityType


@dataclass
class BacktestConfig:
    initial_cash: float = 1_000_000
    days: int = 20                       # 預設回測天數
    strategy_style: str = ""
    risk: RiskConfig = field(default_factory=RiskConfig)
    sec_types: Dict[str, SecurityType] = field(default_factory=dict)


@dataclass
class BacktestResult:
    equity_curve: List[dict] = field(default_factory=list)   # [{date, equity}]
    total_return: float = 0.0
    win_rate: float = 0.0
    expectancy: float = 0.0              # 每筆已實現交易的平均損益
    n_trades: int = 0
    final_equity: float = 0.0


def run_backtest(
    advisor: TradingAdvisor,
    candles_by_symbol: Dict[str, List[dict]],
    config: BacktestConfig,
) -> BacktestResult:
    """逐日回測。candles_by_symbol 為各標的完整日 K（最舊到最新）。"""
    risk_engine = RiskEngine(config.risk)
    dates = _aligned_dates(candles_by_symbol)
    if len(dates) < 2:
        return BacktestResult()

    window = dates[-(config.days + 1):]   # 多留一天供「隔日開盤」成交
    cash = config.initial_cash
    positions: Dict[str, int] = {}
    fills: List[Fill] = []
    equity_curve: List[dict] = []

    for i in range(len(window) - 1):
        decision_date = window[i]
        next_date = window[i + 1]

        # 只餵到 decision_date 為止的 K（不洩漏未來）
        ctx = MarketContext(
            as_of=decision_date,
            candles={
                s: [c for c in cs if c["date"] <= decision_date]
                for s, cs in candles_by_symbol.items()
            },
            quotes=_closes_on(candles_by_symbol, decision_date),
            positions=dict(positions),
            cash=cash,
            strategy_style=config.strategy_style,
        )
        batch = advisor.propose(ctx)

        next_opens = _opens_on(candles_by_symbol, next_date)
        for proposal in batch.proposals:
            if proposal.action == Action.HOLD:
                continue
            fill_price = next_opens.get(proposal.symbol)
            if fill_price is None:
                continue   # 隔日無報價，跳過

            equity = _equity(cash, positions, _closes_on(candles_by_symbol, decision_date))
            sec_type = config.sec_types.get(proposal.symbol, SecurityType.STOCK)
            result = risk_engine.evaluate(
                proposal,
                cash=cash,
                total_equity=equity,
                positions=positions,
                sec_type=sec_type,
            )
            if not result.approved:
                continue

            side = "buy" if proposal.action == Action.BUY else "sell"
            fills.append(
                Fill(
                    symbol=proposal.symbol,
                    side=side,
                    price=fill_price,
                    quantity=proposal.quantity,
                    sec_type=sec_type,
                )
            )
            # est_cost: 買為正、賣為負；現金反向變動
            cash -= result.est_cost
            positions[proposal.symbol] = positions.get(proposal.symbol, 0) + (
                proposal.quantity if side == "buy" else -proposal.quantity
            )

        mark = _closes_on(candles_by_symbol, next_date)
        equity_curve.append({"date": next_date, "equity": _equity(cash, positions, mark)})

    report = compute_pnl(fills, _closes_on(candles_by_symbol, window[-1]))
    final_equity = equity_curve[-1]["equity"] if equity_curve else config.initial_cash
    wins = [t for t in report.realized if t.pnl > 0]

    return BacktestResult(
        equity_curve=equity_curve,
        total_return=(final_equity - config.initial_cash) / config.initial_cash,
        win_rate=(len(wins) / len(report.realized)) if report.realized else 0.0,
        expectancy=(report.realized_pnl / len(report.realized)) if report.realized else 0.0,
        n_trades=len(report.realized),
        final_equity=final_equity,
    )


def _aligned_dates(candles_by_symbol: Dict[str, List[dict]]) -> List[str]:
    dates: set[str] = set()
    for cs in candles_by_symbol.values():
        dates.update(c["date"] for c in cs)
    return sorted(dates)


def _price_on(candles_by_symbol, date, key) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for s, cs in candles_by_symbol.items():
        for c in cs:
            if c["date"] == date:
                out[s] = c[key]
                break
    return out


def _closes_on(candles_by_symbol, date) -> Dict[str, float]:
    return _price_on(candles_by_symbol, date, "close")


def _opens_on(candles_by_symbol, date) -> Dict[str, float]:
    return _price_on(candles_by_symbol, date, "open")


def _equity(cash: float, positions: Dict[str, int], prices: Dict[str, float]) -> float:
    return cash + sum(qty * prices.get(s, 0.0) for s, qty in positions.items())
