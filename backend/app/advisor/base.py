"""TradingAdvisor 介面 — 把「呼叫 AI 做決策」抽象出來。

真正的 Codex 實作只是其中一環。寫測試時可塞入 StubAdvisor，
不必真的呼叫 AI：既省 Token，也不會被網路波動或模型延遲卡住測試。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List

from app.schemas import ProposalBatch


@dataclass
class MarketContext:
    """餵給 advisor 的盤面快照（純資料，不含副作用）。"""

    as_of: str                                   # 決策基準日 YYYY-MM-DD
    candles: Dict[str, List[dict]]               # symbol -> 到 as_of 為止的日 K 序列
    quotes: Dict[str, float] = field(default_factory=dict)   # symbol -> 即時/收盤價
    positions: Dict[str, int] = field(default_factory=dict)  # 現有持股 symbol -> 股數
    cash: float = 0.0
    strategy_style: str = ""                     # 使用者指定的策略風格


class TradingAdvisor(ABC):
    """所有 advisor 的共同介面。"""

    @abstractmethod
    def propose(self, context: MarketContext) -> ProposalBatch:
        """根據盤面提出提案。實作不得在此送出任何委託單。"""
        raise NotImplementedError
