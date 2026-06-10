"""依賴注入 — 在這裡選擇要用的 advisor / 報價來源。

預設用 stub，避免在沒設定金鑰時誤觸真實 API 與 Token 花費。
要切到真實 Codex / Shioaji，改這裡或用環境變數即可。
"""
from __future__ import annotations

import os
from typing import Iterator

from app.advisor.base import TradingAdvisor
from app.advisor.stub import StubAdvisor
from app.db import get_connection
from app.market.shioaji import QuoteSource, StubQuoteSource


def get_db() -> Iterator:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_advisor() -> TradingAdvisor:
    if os.getenv("USE_CODEX") == "1":
        from app.advisor.codex import CodexAdvisor

        return CodexAdvisor()
    return StubAdvisor()


def get_quote_source() -> QuoteSource:
    if os.getenv("USE_SHIOAJI") == "1":
        from app.market.shioaji import ShioajiQuoteSource

        return ShioajiQuoteSource()
    return StubQuoteSource()
