"""StubAdvisor — 測試用樁程式，回傳固定/可預期的提案。

讓「從決策到核准」的整條流程在測試中跑完，不必真的呼叫 AI。
既不燒 Token，也不會被網路或模型延遲卡住。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from app.advisor.base import MarketContext, TradingAdvisor
from app.schemas import Proposal, ProposalBatch


class StubAdvisor(TradingAdvisor):
    def __init__(
        self,
        proposals: Optional[List[Proposal]] = None,
        generator: Optional[Callable[[MarketContext], List[Proposal]]] = None,
    ) -> None:
        """可給固定提案清單，或給一個依 context 產生提案的函式。"""
        self._proposals = proposals or []
        self._generator = generator

    def propose(self, context: MarketContext) -> ProposalBatch:
        proposals = (
            self._generator(context) if self._generator is not None else list(self._proposals)
        )
        return ProposalBatch(proposals=proposals, model_note="stub")
