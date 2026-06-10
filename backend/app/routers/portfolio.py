"""投組路由 — 損益總覽（FIFO，含手續費與證交稅）。"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_quote_source
from app.market.shioaji import QuoteSource
from app.pnl import Fill, compute_pnl
from app.schemas import SecurityType

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class FillIn(BaseModel):
    symbol: str
    side: str
    price: float
    quantity: int
    sec_type: SecurityType = SecurityType.STOCK


class PnLResponse(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    positions: List[dict]
    realized: List[dict]


@router.post("/pnl", response_model=PnLResponse)
def pnl(
    fills: List[FillIn], source: QuoteSource = Depends(get_quote_source)
) -> PnLResponse:
    domain_fills = [
        Fill(f.symbol, f.side, f.price, f.quantity, f.sec_type) for f in fills
    ]
    symbols = sorted({f.symbol for f in domain_fills})
    prices: Dict[str, float] = source.get_quotes(symbols)
    report = compute_pnl(domain_fills, prices)
    return PnLResponse(
        realized_pnl=report.realized_pnl,
        unrealized_pnl=report.unrealized_pnl,
        total_pnl=report.total_pnl,
        positions=[p.__dict__ for p in report.positions],
        realized=[t.__dict__ for t in report.realized],
    )
