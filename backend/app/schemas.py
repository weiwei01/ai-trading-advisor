"""Pydantic schemas — 穩定層的契約。

AI 回傳的提案必須通過這裡的嚴格驗證才會進入後續流程：
價格 > 0、數量為正整數、信心分數落在 0~1、理由不可空白。
任何不合規的輸出都會在這層被擋下，作為對 LLM 格式不穩定/幻覺的第一道防線。
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class MarketType(str, Enum):
    TSE = "tse"   # 上市
    OTC = "otc"   # 上櫃


class SecurityType(str, Enum):
    STOCK = "stock"
    ETF = "etf"


class Proposal(BaseModel):
    """AI 對單一標的的進出場提案。經 Pydantic 驗證後才算有效。"""

    symbol: str = Field(..., min_length=1, description="股票代號，如 2330")
    action: Action
    price: float = Field(..., gt=0, description="建議成交價，必須大於 0")
    quantity: int = Field(..., gt=0, description="股數，必須為正整數")
    confidence: float = Field(..., ge=0.0, le=1.0, description="信心分數 0~1")
    reason: str = Field(..., min_length=1, description="進場理由，不可空白")
    risk_note: str = Field(..., min_length=1, description="風險條件，不可空白")
    stop_loss: Optional[float] = Field(None, gt=0, description="停損價")
    take_profit: Optional[float] = Field(None, gt=0, description="停利價")

    @field_validator("reason", "risk_note")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("不可為空白")
        return v.strip()

    @field_validator("symbol")
    @classmethod
    def _clean_symbol(cls, v: str) -> str:
        return v.strip()


class ProposalBatch(BaseModel):
    """一次決策可能對多檔標的提案。"""

    proposals: List[Proposal] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_note: str = ""


class ProposalDecision(str, Enum):
    """人類對 AI 提案的最終裁決 — 系統不會自動下單。"""

    PENDING = "pending"
    APPROVED = "approved"   # 人類核准（仍由人手動送單）
    REJECTED = "rejected"


class StoredProposal(Proposal):
    id: int
    decision: ProposalDecision = ProposalDecision.PENDING
    created_at: datetime
