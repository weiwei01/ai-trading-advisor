"""依賴注入 — 在這裡選擇要用的 advisor / 報價來源。

預設用 stub，避免在沒設定金鑰時誤觸真實 API 與 Token 花費。
要切到真實 Codex / Shioaji，改這裡或用環境變數即可。
"""
from __future__ import annotations

from typing import Iterator

from app import config
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
    if config.USE_CODEX:
        from app.advisor.codex import CodexAdvisor

        return CodexAdvisor()
    if config.USE_RULES:
        from app.advisor.rules import RuleBasedAdvisor

        return RuleBasedAdvisor()
    return StubAdvisor()


def get_quote_source() -> QuoteSource:
    if config.USE_SHIOAJI:
        from app.market.shioaji import ShioajiQuoteSource

        return ShioajiQuoteSource()
    return StubQuoteSource()
