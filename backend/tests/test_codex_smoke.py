"""Smoke test — 唯一真正呼叫 Codex 的測試。

用 @pytest.mark.smoke 標記，預設不跑（pytest.ini 已排除）。
要跑：先設好 OPENAI_API_KEY，再執行 `pytest -m smoke`。
這層只驗證「真的能拿到一個通過 schema 驗證的回應」，不驗證內容好壞。
"""
import os

import pytest

from app.advisor.base import MarketContext

pytestmark = pytest.mark.smoke


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY")
def test_codex_returns_valid_batch():
    from app.advisor.codex import CodexAdvisor

    advisor = CodexAdvisor()
    ctx = MarketContext(
        as_of="2024-06-03",
        candles={"2330": [
            {"date": "2024-06-03", "open": 800, "high": 810,
             "low": 795, "close": 805, "volume": 20000},
        ]},
        quotes={"2330": 805},
        cash=1_000_000,
        strategy_style="穩健波段",
    )
    batch = advisor.propose(ctx)   # 解析+驗證若失敗會丟例外
    assert batch is not None
