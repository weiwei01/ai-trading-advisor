"""回測路由。預設用 stub advisor；要用真實 Codex 設 USE_CODEX=1（會燒 Token）。"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.advisor.base import TradingAdvisor
from app.backtest import BacktestConfig, BacktestResult, run_backtest
from app.deps import get_advisor, get_db
from app.market import repository as market_repo
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
    trades: List[dict]


def _to_response(result: BacktestResult) -> BacktestResponse:
    return BacktestResponse(
        total_return=result.total_return,
        win_rate=result.win_rate,
        expectancy=result.expectancy,
        n_trades=result.n_trades,
        final_equity=result.final_equity,
        equity_curve=result.equity_curve,
        trades=result.trades,
    )


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
    return _to_response(run_backtest(advisor, req.candles, config))


class StoredBacktestRequest(BaseModel):
    """用 DB 已存日 K 跑回測 — 前端不必自己組 candles。"""

    symbols: List[str] = []          # 空 = DB 內全部
    initial_cash: float = 1_000_000
    days: int = 20
    strategy_style: str = ""
    etf_symbols: List[str] = []


@router.post("/run-stored", response_model=BacktestResponse)
def run_stored(
    req: StoredBacktestRequest,
    advisor: TradingAdvisor = Depends(get_advisor),
    conn=Depends(get_db),
) -> BacktestResponse:
    symbols = req.symbols or market_repo.stored_symbols(conn)
    candles = market_repo.load_many(conn, symbols)
    config = BacktestConfig(
        initial_cash=req.initial_cash,
        days=req.days,
        strategy_style=req.strategy_style,
        sec_types={s: SecurityType.ETF for s in req.etf_symbols},
    )
    return _to_response(run_backtest(advisor, candles, config))


@router.get("/symbols", response_model=List[str])
def symbols(conn=Depends(get_db)) -> List[str]:
    """DB 內已有日 K 的標的清單。"""
    return market_repo.stored_symbols(conn)
