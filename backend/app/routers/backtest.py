"""回測路由。預設用 stub advisor；要用真實 Codex 設 USE_CODEX=1（會燒 Token）。"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.advisor.base import TradingAdvisor
from app.backtest import BacktestConfig, run_backtest
from app.deps import get_advisor
from app.schemas import SecurityType

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    candles: Dict[str, List[dict]]
    initial_cash: float = 1_000_000
    days: int = 20
    strategy_style: str = ""
    sec_types: Dict[str, SecurityType] = {}


class BacktestResponse(BaseModel):
    total_return: float
    win_rate: float
    expectancy: float
    n_trades: int
    final_equity: float
    equity_curve: List[dict]


@router.post("/run", response_model=BacktestResponse)
def run(
    req: BacktestRequest, advisor: TradingAdvisor = Depends(get_advisor)
) -> BacktestResponse:
    config = BacktestConfig(
        initial_cash=req.initial_cash,
        days=req.days,
        strategy_style=req.strategy_style,
        sec_types=req.sec_types,
    )
    result = run_backtest(advisor, req.candles, config)
    return BacktestResponse(
        total_return=result.total_return,
        win_rate=result.win_rate,
        expectancy=result.expectancy,
        n_trades=result.n_trades,
        final_equity=result.final_equity,
        equity_curve=result.equity_curve,
    )
