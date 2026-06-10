"""風控引擎 — 實盤與回測共用同一套規則。

把 AI 提案逐筆過風控：超出規則的直接擋下並附原因。
這層不送單，只負責「這筆提案是否允許進入可核准狀態」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.pnl import brokerage_fee, transaction_tax
from app.schemas import Action, Proposal, SecurityType


@dataclass
class RiskConfig:
    max_position_pct: float = 0.25     # 單一標的市值上限佔總資產比例
    max_order_value: float = 500_000   # 單筆委託金額上限
    min_confidence: float = 0.5        # 低於此信心分數的提案一律擋下
    allow_short: bool = False          # 是否允許無持股賣出（做空）


@dataclass
class RiskResult:
    proposal: Proposal
    approved: bool
    reasons: List[str] = field(default_factory=list)
    est_cost: float = 0.0   # 含費用的預估金額


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(
        self,
        proposal: Proposal,
        *,
        cash: float,
        total_equity: float,
        positions: Dict[str, int],
        sec_type: SecurityType = SecurityType.STOCK,
    ) -> RiskResult:
        cfg = self.config
        reasons: List[str] = []
        gross = proposal.price * proposal.quantity

        if proposal.action == Action.HOLD:
            return RiskResult(proposal=proposal, approved=False, reasons=["hold 不產生委託"])

        if proposal.confidence < cfg.min_confidence:
            reasons.append(f"信心分數 {proposal.confidence:.2f} 低於門檻 {cfg.min_confidence}")

        if gross > cfg.max_order_value:
            reasons.append(f"單筆金額 {gross:.0f} 超過上限 {cfg.max_order_value:.0f}")

        if proposal.action == Action.BUY:
            fee = brokerage_fee(gross)
            est_cost = gross + fee
            if est_cost > cash:
                reasons.append(f"現金不足：需 {est_cost:.0f}，可用 {cash:.0f}")
            if total_equity > 0:
                pct = gross / total_equity
                if pct > cfg.max_position_pct:
                    reasons.append(
                        f"部位佔比 {pct:.0%} 超過上限 {cfg.max_position_pct:.0%}"
                    )
            return RiskResult(
                proposal=proposal,
                approved=not reasons,
                reasons=reasons,
                est_cost=est_cost,
            )

        # SELL
        held = positions.get(proposal.symbol, 0)
        if proposal.quantity > held and not cfg.allow_short:
            reasons.append(f"賣出 {proposal.quantity} 股超過持有 {held} 股")
        fee = brokerage_fee(gross)
        tax = transaction_tax(gross, sec_type)
        est_proceeds = gross - fee - tax
        return RiskResult(
            proposal=proposal,
            approved=not reasons,
            reasons=reasons,
            est_cost=-est_proceeds,
        )
