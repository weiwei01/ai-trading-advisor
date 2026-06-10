"""證交所公開 API — 每日 K 棒歷史趨勢。

只負責抓取與整形成統一的 candle dict，不含決策邏輯。
"""
from __future__ import annotations

from typing import List

import httpx

# 月成交資訊（含每日 K）：STOCK_DAY
_BASE = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"


def fetch_daily_candles(symbol: str, yyyymm: str) -> List[dict]:
    """抓取某月每日 K 棒。yyyymm 例如 '20240601'（該月任一日）。

    回傳統一格式：{date, open, high, low, close, volume}。
    """
    params = {"response": "json", "date": yyyymm, "stockNo": symbol}
    resp = httpx.get(_BASE, params=params, timeout=10.0)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("stat") != "OK":
        return []
    return [_parse_row(r) for r in payload.get("data", [])]


def _parse_row(row: List[str]) -> dict:
    # row: 日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌價差, 成交筆數
    def num(s: str) -> float:
        return float(s.replace(",", "")) if s.strip() not in ("", "--") else 0.0

    return {
        "date": _roc_to_iso(row[0]),
        "volume": num(row[1]),
        "open": num(row[3]),
        "high": num(row[4]),
        "low": num(row[5]),
        "close": num(row[6]),
    }


def _roc_to_iso(roc: str) -> str:
    """民國日期 '113/06/03' -> '2024-06-03'。"""
    y, m, d = roc.split("/")
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}"
