"""穩定層：組 prompt / 解析回應 / 定義 schema。

全部都是純函式 — 同樣輸入永遠得到同樣輸出，不碰網路也不碰模型隨機性。
真正會碰到網路與模型隨機性的，只剩 codex.py 裡實際呼叫 Codex 那一段。
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.schemas import ProposalBatch

if TYPE_CHECKING:
    from app.advisor.base import MarketContext


SYSTEM_PROMPT = """你是一位嚴謹的台股交易研究助理。你的職責是「研究與提案」，不是下單。
根據提供的盤面資料與策略風格，對標的提出進出場提案，並為每一筆寫出明確的理由與風險條件。
請務必：
- 只依據提供的資料推論，不得臆測未提供的數字。
- 信心分數誠實反映把握程度（0~1），不要一律給高分。
- 若無明確機會，回傳空的 proposals 陣列即可，不要硬湊。
僅以 JSON 回覆，不要任何額外文字。"""


def build_prompt(context: "MarketContext") -> str:
    """把盤面快照組成給模型的 user prompt（純函式）。"""
    lines = [
        f"決策基準日：{context.as_of}",
        f"策略風格：{context.strategy_style or '（未指定，採穩健中性）'}",
        f"可用現金：{context.cash:.0f}",
        f"現有持股：{json.dumps(context.positions, ensure_ascii=False)}",
        "",
        "各標的日 K 序列（到基準日為止，最舊到最新）：",
    ]
    for symbol, candles in context.candles.items():
        quote = context.quotes.get(symbol)
        head = f"- {symbol}" + (f"（最新報價 {quote}）" if quote is not None else "")
        lines.append(head)
        lines.append(f"  {json.dumps(candles[-30:], ensure_ascii=False)}")
    lines += [
        "",
        "請回傳如下 JSON 結構：",
        '{"proposals": [{"symbol": "2330", "action": "buy", "price": 0, '
        '"quantity": 0, "confidence": 0.0, "reason": "", "risk_note": "", '
        '"stop_loss": null, "take_profit": null}], "model_note": ""}',
    ]
    return "\n".join(lines)


def parse_response(raw: str) -> ProposalBatch:
    """把模型回傳的字串解析並驗證成 ProposalBatch（純函式）。

    任何 JSON 解析失敗或 Pydantic 驗證失敗都會丟出例外，由呼叫端決定如何處理。
    """
    text = _strip_code_fence(raw).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型回應不是合法 JSON：{exc}") from exc

    if isinstance(data, list):
        data = {"proposals": data}

    try:
        return ProposalBatch.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"提案未通過 schema 驗證：{exc}") from exc


def _strip_code_fence(text: str) -> str:
    """移除模型常見的 ```json ... ``` 包裹。"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    return t
