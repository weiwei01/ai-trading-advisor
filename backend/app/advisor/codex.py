"""CodexAdvisor — 真正呼叫 OpenAI LLM 的 TradingAdvisor。

機制：
- 快照雜湊快取：避免同一天、同一狀態重跑回測重複呼叫。
- Token 統計：紀錄每次調用的 Token 數量，存入 token_usage 表。
- 容錯降級：呼叫超時或失敗時，當天自動視為 HOLD（回傳空 proposals），維持流程不中斷。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from app import config
from app.advisor.base import MarketContext, TradingAdvisor
from app.advisor.prompt import SYSTEM_PROMPT, build_prompt, parse_response
from app.db import get_connection
from app.repository import (
    get_backtest_cache,
    log_token_usage,
    save_backtest_cache,
)
from app.schemas import ProposalBatch


class CodexAdvisor(TradingAdvisor):
    def __init__(self, model: str | None = None, api_key: Optional[str] = None) -> None:
        self.model = model or config.CODEX_MODEL
        self._api_key = api_key or config.OPENAI_API_KEY

    def propose(self, context: MarketContext) -> ProposalBatch:
        # 1. 計算 context_hash
        ctx_hash = self._get_context_hash(context)

        # 2. 檢查資料庫快取
        try:
            conn = get_connection()
            cached_resp = get_backtest_cache(conn, ctx_hash)
            conn.close()
            if cached_resp:
                return parse_response(cached_resp)
        except Exception as e:
            print(f"[警告] 讀取回測快取失敗: {e}")

        # 3. 呼叫模型 (含容錯降級)
        prompt = build_prompt(context)
        try:
            raw, prompt_tokens, completion_tokens = self._call_model(prompt)
        except Exception as exc:
            # 容錯降級策略：失敗或超時當天視為 HOLD
            print(f"[警告] Codex 呼叫失敗，啟用降級策略 (當天視為 HOLD)。錯誤: {exc}")
            return ProposalBatch(proposals=[], model_note="degraded-fallback")

        # 4. 解析與驗證
        try:
            batch = parse_response(raw)
        except Exception as exc:
            print(f"[警告] Codex 回應解析失敗: {exc}")
            return ProposalBatch(proposals=[], model_note="parse-failed-fallback")

        # 5. 寫入快取與統計
        try:
            conn = get_connection()
            save_backtest_cache(conn, ctx_hash, raw)
            log_token_usage(conn, self.model, prompt_tokens, completion_tokens)
            conn.close()
        except Exception as e:
            print(f"[警告] 寫入快取與統計失敗: {e}")

        return batch

    def _call_model(self, user_prompt: str) -> tuple[str, int, int]:
        """呼叫 OpenAI Chat Completions API。

        回傳元組：(回應文字, prompt_tokens, completion_tokens)
        """
        from openai import OpenAI  # 延遲匯入

        if not self._api_key:
            raise ValueError("未設定 OPENAI_API_KEY 環境變數，無法呼叫 LLM 服務。")

        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        output_text = resp.choices[0].message.content or ""
        prompt_tokens = resp.usage.prompt_tokens
        completion_tokens = resp.usage.completion_tokens
        return output_text, prompt_tokens, completion_tokens

    def _get_context_hash(self, context: MarketContext) -> str:
        """為 MarketContext 計算唯一的雜湊值。"""
        # 只保留關鍵數據，避免雜湊不一致
        normalized_candles = {}
        for s, cs in context.candles.items():
            normalized_candles[s] = [
                {"date": c["date"], "close": c["close"]} for c in cs[-30:]
            ]

        data = {
            "as_of": context.as_of,
            "candles": normalized_candles,
            "quotes": context.quotes,
            "positions": context.positions,
            "cash": context.cash,
            "strategy_style": context.strategy_style,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
