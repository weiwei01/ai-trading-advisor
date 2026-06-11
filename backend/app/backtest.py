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


from datetime import datetime
from app.pnl import brokerage_fee, transaction_tax

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
    trades: List[dict] = field(default_factory=list)         # 逐筆成交事件（除錯用）
    total_return: float = 0.0
    win_rate: float = 0.0
    expectancy: float = 0.0              # 每筆已實現交易的平均損益
    n_trades: int = 0
    final_equity: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    avg_holding_days: float = 0.0
    tx_cost_ratio: float = 0.0           # 交易成本佔獲利比


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
    trades: List[dict] = []
    equity_curve: List[dict] = []

    # 初始權益（第 0 天）
    first_date = window[0]
    initial_mark = _closes_on(candles_by_symbol, first_date)
    equity_curve.append({"date": first_date, "equity": _equity(cash, positions, initial_mark)})

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
                    date=next_date,
                )
            )
            # est_cost: 買為正、賣為負；現金反向變動
            cash -= result.est_cost
            positions[proposal.symbol] = positions.get(proposal.symbol, 0) + (
                proposal.quantity if side == "buy" else -proposal.quantity
            )
            # 成交事件：除錯圖用 — 決策日、成交日、隔日開盤價、提案理由
            trades.append({
                "decision_date": decision_date,
                "fill_date": next_date,
                "symbol": proposal.symbol,
                "side": side,
                "price": fill_price,
                "quantity": proposal.quantity,
                "reason": proposal.reason,
            })

        mark = _closes_on(candles_by_symbol, next_date)
        equity_curve.append({"date": next_date, "equity": _equity(cash, positions, mark)})

    report = compute_pnl(fills, _closes_on(candles_by_symbol, window[-1]))
    final_equity = equity_curve[-1]["equity"] if equity_curve else config.initial_cash
    wins = [t for t in report.realized if t.pnl > 0]

    # 1. Max Drawdown (MDD)
    peak = -float("inf")
    max_dd = 0.0
    for ep in equity_curve:
        eq = ep["equity"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # 2. Sharpe Ratio
    sharpe = 0.0
    if len(equity_curve) >= 2:
        returns = []
        for i in range(1, len(equity_curve)):
            prev_eq = equity_curve[i - 1]["equity"]
            curr_eq = equity_curve[i]["equity"]
            returns.append((curr_eq - prev_eq) / prev_eq if prev_eq > 0 else 0.0)
        
        n = len(returns)
        if n > 0:
            mean_ret = sum(returns) / n
            variance = sum((r - mean_ret) ** 2 for r in returns) / n
            std_ret = variance ** 0.5
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * (252 ** 0.5)

    # 3. Average Holding Days
    def _days_between(d1_str: str, d2_str: str) -> float:
        try:
            t1 = datetime.strptime(d1_str, "%Y-%m-%d")
            t2 = datetime.strptime(d2_str, "%Y-%m-%d")
            return float((t2 - t1).days)
        except Exception:
            return 0.0

    holding_days = [_days_between(t.buy_date, t.sell_date) for t in report.realized if t.buy_date and t.sell_date]
    avg_holding = sum(holding_days) / len(holding_days) if holding_days else 0.0

    # 4. Transaction Cost Ratio
    total_tx_costs = 0.0
    for f in fills:
        gross = f.price * f.quantity
        total_tx_costs += brokerage_fee(gross)
        if f.side == "sell":
            total_tx_costs += transaction_tax(gross, f.sec_type)
    
    realized_gains = sum(t.pnl for t in report.realized if t.pnl > 0)
    tx_ratio = total_tx_costs / realized_gains if realized_gains > 0 else 0.0

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        total_return=(final_equity - config.initial_cash) / config.initial_cash,
        win_rate=(len(wins) / len(report.realized)) if report.realized else 0.0,
        expectancy=(report.realized_pnl / len(report.realized)) if report.realized else 0.0,
        n_trades=len(report.realized),
        final_equity=final_equity,
        max_drawdown=max_dd,
        sharpe_ratio=sharpe,
        avg_holding_days=avg_holding,
        tx_cost_ratio=tx_ratio,
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
