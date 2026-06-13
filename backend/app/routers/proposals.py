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
from app.deps import get_advisor, get_db, get_quote_source
from app.market.shioaji import QuoteSource
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


class GenerateFromDbRequest(BaseModel):
    """頁面一鍵產生：用 DB 已存日 K + 成交紀錄，不即時連網。"""

    as_of: Optional[str] = None       # 決策基準日；省略=最新有資料的一天
    strategy_style: str = "穩健中性"
    initial_cash: float = 1_000_000.0
    advisor: str = "rules"            # rules（不燒 Token）/ codex（真實 AI）/ stub


def _build_advisor(name: str) -> TradingAdvisor:
    if name == "codex":
        from app.advisor.codex import CodexAdvisor
        return CodexAdvisor()
    if name == "stub":
        from app.advisor.stub import StubAdvisor
        return StubAdvisor()
    from app.advisor.rules import RuleBasedAdvisor
    return RuleBasedAdvisor()


class GenerateFromDbResponse(GenerateResponse):
    as_of: str
    advisor: str                      # 這次用哪個 advisor（stub/rules/codex）
    n_proposed: int                   # advisor 原始提案數（含被擋）


@router.post("/generate-from-db", response_model=GenerateFromDbResponse)
def generate_from_db(
    req: GenerateFromDbRequest,
    conn=Depends(get_db),
) -> GenerateFromDbResponse:
    """從本機已存資料直接產生提案——前端按鈕用。不送出任何委託單。"""
    from app import config
    from app.market import repository as market_repo
    from app.pnl import Fill, current_cash_and_positions
    from app.schemas import SecurityType

    advisor = _build_advisor(req.advisor)
    symbols = market_repo.stored_symbols(conn)
    if not symbols:
        raise HTTPException(status_code=400, detail="DB 內沒有任何日 K，請先抓取行情")

    # 決策基準日：預設取所有資料中最新的一天
    all_candles = market_repo.load_many(conn, symbols)
    if req.as_of:
        as_of = req.as_of
    else:
        as_of = max(c["date"] for cs in all_candles.values() for c in cs)

    # 帳戶現況：從成交紀錄推算（list_fills 為新→舊，反轉成時間正序）
    db_fills = list(reversed(repository.list_fills(conn)))
    fills = [
        Fill(f["symbol"], f["side"], f["price"], f["quantity"], SecurityType(f["sec_type"]))
        for f in db_fills
    ]
    cash, positions = current_cash_and_positions(fills, req.initial_cash)

    # 只餵到 as_of 為止的 K（不洩漏未來）；報價用當日收盤
    candles_ctx = {s: [c for c in cs if c["date"] <= as_of] for s, cs in all_candles.items()}
    quotes = {
        s: next((c["close"] for c in reversed(cs) if c["date"] <= as_of), 0.0)
        for s, cs in all_candles.items()
    }

    ctx = MarketContext(
        as_of=as_of, candles=candles_ctx, quotes=quotes,
        positions=positions, cash=cash, strategy_style=req.strategy_style,
    )
    batch = advisor.propose(ctx)

    engine = RiskEngine(RiskConfig(
        max_position_pct=config.MAX_POSITION_PCT,
        max_order_value=config.MAX_ORDER_VALUE,
        min_confidence=config.MIN_CONFIDENCE,
        allow_short=config.ALLOW_SHORT,
    ))
    equity = cash + sum(positions.get(s, 0) * quotes.get(s, 0.0) for s in positions)
    saved_ids: List[int] = []
    blocked: List[dict] = []
    for p in batch.proposals:
        meta = repository.get_security_metadata(conn, p.symbol)
        sec_type = SecurityType(meta["sec_type"]) if meta else SecurityType.STOCK
        result = engine.evaluate(
            p, cash=cash, total_equity=equity, positions=positions, sec_type=sec_type
        )
        if result.approved:
            saved_ids.append(repository.save_proposal(conn, p))
        else:
            blocked.append({"symbol": p.symbol, "reasons": result.reasons})

    return GenerateFromDbResponse(
        saved_ids=saved_ids, blocked=blocked, as_of=as_of,
        advisor=type(advisor).__name__, n_proposed=len(batch.proposals),
    )


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
