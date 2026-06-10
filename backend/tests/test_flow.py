"""端到端流程測試 — 用 StubAdvisor 跑完「決策 -> 風控 -> 入庫 -> 人類裁決」。

不呼叫真實 AI：不燒 Token，也不受網路波動影響。
"""
from app.advisor.base import MarketContext
from app.advisor.stub import StubAdvisor
from app.db import temp_db
from app.repository import list_proposals, save_proposal, set_decision
from app.risk import RiskConfig, RiskEngine
from app.schemas import Proposal, ProposalDecision


def _proposal(**kw):
    base = dict(
        symbol="2330", action="buy", price=100.0, quantity=1000,
        confidence=0.8, reason="測試理由", risk_note="測試風險",
    )
    base.update(kw)
    return Proposal(**base)


def test_decision_to_human_approval_flow():
    advisor = StubAdvisor(proposals=[_proposal()])
    ctx = MarketContext(as_of="2024-06-03", candles={"2330": []}, cash=1_000_000)
    batch = advisor.propose(ctx)
    assert len(batch.proposals) == 1

    engine = RiskEngine(RiskConfig())
    with temp_db() as conn:
        for p in batch.proposals:
            r = engine.evaluate(p, cash=1_000_000, total_equity=1_000_000, positions={})
            assert r.approved
            save_proposal(conn, p)

        pending = list_proposals(conn, ProposalDecision.PENDING)
        assert len(pending) == 1

        # 人類核准（系統不自動下單）
        assert set_decision(conn, pending[0].id, ProposalDecision.APPROVED)
        approved = list_proposals(conn, ProposalDecision.APPROVED)
        assert len(approved) == 1


def test_risk_blocks_low_confidence_and_insufficient_cash():
    engine = RiskEngine(RiskConfig(min_confidence=0.5))
    low_conf = engine.evaluate(
        _proposal(confidence=0.2), cash=1_000_000, total_equity=1_000_000, positions={}
    )
    assert not low_conf.approved

    too_big = engine.evaluate(
        _proposal(price=100.0, quantity=1000),
        cash=1000, total_equity=1000, positions={},
    )
    assert not too_big.approved
