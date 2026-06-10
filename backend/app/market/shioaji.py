"""永豐 Shioaji API — 盤中即時報價。

抽成 QuoteSource 介面，實作可換成 stub（測試/回測用）或真實 Shioaji。
注意：本系統定位為決策輔助，這裡只取報價，絕不送出任何委託單。
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class QuoteSource(ABC):
    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> Dict[str, float]:
        """回傳 symbol -> 最新成交價。"""
        raise NotImplementedError


class StubQuoteSource(QuoteSource):
    """測試/回測用：回傳預設好的價格。"""

    def __init__(self, prices: Optional[Dict[str, float]] = None) -> None:
        self._prices = prices or {}

    def set(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def get_quotes(self, symbols: List[str]) -> Dict[str, float]:
        return {s: self._prices[s] for s in symbols if s in self._prices}


class ShioajiQuoteSource(QuoteSource):
    """真實 Shioaji 報價來源。延遲匯入 SDK，缺套件時不影響其餘模組。"""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("SHIOAJI_API_KEY")
        self._secret_key = secret_key or os.getenv("SHIOAJI_SECRET_KEY")
        self._api = None

    def _ensure_login(self):
        if self._api is None:
            import shioaji as sj  # 延遲匯入

            self._api = sj.Shioaji()
            self._api.login(api_key=self._api_key, secret_key=self._secret_key)
        return self._api

    def get_quotes(self, symbols: List[str]) -> Dict[str, float]:
        api = self._ensure_login()
        out: Dict[str, float] = {}
        for s in symbols:
            contract = api.Contracts.Stocks[s]
            snapshot = api.snapshots([contract])[0]
            out[s] = float(snapshot.close)
        return out
