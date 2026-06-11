"""提案路由 — 產生提案、列出待裁決、人類核准/婉拒。

注意：核准（approve）只是把提案標記為「人類已同意」，系統不會送單。
實際下單仍由使用者在券商端手動執行。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import repository
from app.advisor.base import MarketContext, TradingAdvisor
from app.deps import get_advisor, get_db
from app.risk import RiskConfig, RiskEngine
from app.schemas import ProposalDecision, StoredProposal

router = APIRouter(prefix="/proposals", tags=["proposals"])


class GenerateRequest(BaseModel):
    as_of: str
    candles: dict
    quotes: dict = {}
    positions: dict = {}
    cash: float = 0.0
    strategy_style: str = ""


class GenerateResponse(BaseModel):
    saved_ids: List[int]
    blocked: List[dict]   # 未通過風控的提案與原因


@router.post("/generate", response_model=GenerateResponse)
def generate(
    req: GenerateRequest,
    advisor: TradingAdvisor = Depends(get_advisor),
    conn=Depends(get_db),
) -> GenerateResponse:
    ctx = MarketContext(
        as_of=req.as_of,
        candles=req.candles,
        quotes=req.quotes,
        positions=req.positions,
        cash=req.cash,
        strategy_style=req.strategy_style,
    )
    batch = advisor.propose(ctx)   # 提案已在 parse 時過 Pydantic 驗證

    engine = RiskEngine(RiskConfig())
    equity = req.cash + sum(
        req.positions.get(s, 0) * req.quotes.get(s, 0.0) for s in req.positions
    )
    saved_ids: List[int] = []
    blocked: List[dict] = []
    for p in batch.proposals:
        result = engine.evaluate(
            p, cash=req.cash, total_equity=equity, positions=req.positions
        )
        if result.approved:
            saved_ids.append(repository.save_proposal(conn, p))
        else:
            blocked.append({"symbol": p.symbol, "reasons": result.reasons})
    return GenerateResponse(saved_ids=saved_ids, blocked=blocked)


@router.get("", response_model=List[StoredProposal])
def list_all(
    decision: Optional[ProposalDecision] = None, conn=Depends(get_db)
) -> List[StoredProposal]:
    return repository.list_proposals(conn, decision)


@router.get("/tracking", response_model=List[dict])
def track_proposals(
    conn=Depends(get_db),
    source: QuoteSource = Depends(get_quote_source),
) -> List[dict]:
    """追蹤提案的事後表現（包含已同意與已婉拒的對照分析）。"""
    from app.market import repository as market_repo
    
    props = repository.list_proposals(conn)
    symbols = sorted({p.symbol for p in props})
    current_quotes = source.get_quotes(symbols)
    
    # Fallback to last close from DB
    for s in symbols:
        if s not in current_quotes or current_quotes[s] <= 0:
            s_candles = market_repo.load_candles(conn, s)
            if s_candles:
                current_quotes[s] = s_candles[-1]["close"]
            else:
                current_quotes[s] = 0.0

    out = []
    for p in props:
        curr_price = current_quotes.get(p.symbol, 0.0)
        hypo_return = 0.0
        if p.price > 0 and curr_price > 0:
            if p.action == "buy":
                hypo_return = (curr_price - p.price) / p.price
            elif p.action == "sell":
                # 賣出提案：計算如果「未賣出」的價格變動（若跌，代表賣出決定是正確的，規避了損失）
                hypo_return = (p.price - curr_price) / p.price

        out.append({
            "id": p.id,
            "symbol": p.symbol,
            "action": p.action.value,
            "price": p.price,
            "quantity": p.quantity,
            "confidence": p.confidence,
            "reason": p.reason,
            "risk_note": p.risk_note,
            "decision": p.decision.value,
            "created_at": p.created_at,
            "current_price": curr_price,
            "hypothetical_return": hypo_return,
        })
    return out


class DecisionRequest(BaseModel):
    decision: ProposalDecision


@router.post("/{proposal_id}/decision", response_model=StoredProposal)
def decide(proposal_id: int, req: DecisionRequest, conn=Depends(get_db)) -> StoredProposal:
    if not repository.set_decision(conn, proposal_id, req.decision):
        raise HTTPException(status_code=404, detail="提案不存在")
    items = [p for p in repository.list_proposals(conn) if p.id == proposal_id]
    return items[0]
