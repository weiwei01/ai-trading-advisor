"""CodexAdvisor — 非穩定層。唯一真正碰到網路與模型隨機性的地方。

呼叫 OpenAI Codex SDK 取得回應後，立刻交回穩定層的 parse_response 做解析與驗證。
這一段以 smoke test 處理，不納入一般單元測試（避免燒 Token / 受網路波動影響）。
"""
from __future__ import annotations

import os
from typing import Optional

from app.advisor.base import MarketContext, TradingAdvisor
from app.advisor.prompt import SYSTEM_PROMPT, build_prompt, parse_response
from app.schemas import ProposalBatch


class CodexAdvisor(TradingAdvisor):
    def __init__(self, model: str = "gpt-5-codex", api_key: Optional[str] = None) -> None:
        self.model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")

    def propose(self, context: MarketContext) -> ProposalBatch:
        raw = self._call_model(build_prompt(context))
        # 解析與驗證回到穩定層；驗證失敗會丟例外，由呼叫端決定如何降級處理。
        return parse_response(raw)

    def _call_model(self, user_prompt: str) -> str:
        """實際呼叫 — 唯一的非穩定點。延遲匯入 SDK，缺套件時不影響其餘模組。"""
        from openai import OpenAI  # 延遲匯入

        client = OpenAI(api_key=self._api_key)
        resp = client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
        )
        return resp.output_text
