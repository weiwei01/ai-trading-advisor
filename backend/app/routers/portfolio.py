"""投組路由 — 損益總覽（FIFO，含手續費與證交稅）。"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_quote_source, get_db
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


@router.get("/pnl", response_model=PnLResponse)
def get_stored_pnl(
    conn=Depends(get_db),
    source: QuoteSource = Depends(get_quote_source),
) -> PnLResponse:
    from app.repository import list_fills
    from app.market import repository as market_repo
    
    # list_fills 為顯示用的新→舊排序；FIFO 需要舊→新（時間正序），故反轉
    db_fills = list(reversed(list_fills(conn)))
    domain_fills = [
        Fill(
            symbol=f["symbol"],
            side=f["side"],
            price=f["price"],
            quantity=f["quantity"],
            sec_type=SecurityType(f["sec_type"]),
        )
        for f in db_fills
    ]
    symbols = sorted({f.symbol for f in domain_fills})
    quotes: Dict[str, float] = source.get_quotes(symbols)
    
    # Fallback to last close from DB
    for s in symbols:
        if s not in quotes or quotes[s] <= 0:
            s_candles = market_repo.load_candles(conn, s)
            if s_candles:
                quotes[s] = s_candles[-1]["close"]
            else:
                quotes[s] = 0.0

    report = compute_pnl(domain_fills, quotes)
    return PnLResponse(
        realized_pnl=report.realized_pnl,
        unrealized_pnl=report.unrealized_pnl,
        total_pnl=report.total_pnl,
        positions=[p.__dict__ for p in report.positions],
        realized=[t.__dict__ for t in report.realized],
    )


@router.post("/fills", response_model=dict)
def add_manual_fill(f: FillIn, conn=Depends(get_db)) -> dict:
    from app.repository import save_fill
    fill_id = save_fill(
        conn,
        symbol=f.symbol,
        side=f.side,
        price=f.price,
        quantity=f.quantity,
        sec_type=f.sec_type.value,
    )
    return {"id": fill_id, "status": "saved"}


@router.get("/fills", response_model=List[dict])
def get_fills_list(conn=Depends(get_db)) -> List[dict]:
    from app.repository import list_fills
    return list_fills(conn)
