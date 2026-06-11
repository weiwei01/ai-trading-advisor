"""櫃買中心 (TPEx) API — 每日 K 棒歷史趨勢 (上櫃標的)。"""
from __future__ import annotations

import httpx
from typing import List

_BASE = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"


def fetch_otc_daily_candles(symbol: str, yyyymm: str) -> List[dict]:
    """抓取上櫃某月每日 K 棒。yyyymm 例如 '20240601'。
    
    回傳統一格式：{date, open, high, low, close, volume}。
    """
    y = yyyymm[:4]
    m = yyyymm[4:6]
    # 格式必須是 YYYY/MM/01
    date_param = f"{y}/{m}/01"

    params = {"code": symbol, "date": date_param}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43.php"
    }
    
    resp = httpx.get(_BASE, params=params, headers=headers, timeout=10.0, follow_redirects=True)
    resp.raise_for_status()
    payload = resp.json()
    
    if payload.get("stat") != "ok" or not payload.get("tables"):
        return []
        
    table_data = payload["tables"][0].get("data", [])
    return [_parse_row(r) for r in table_data]


def _parse_row(row: List[str]) -> dict:
    # row 格式: 日期, 成交仟股, 成交仟元, 開盤, 最高, 最低, 收盤, 漲跌, 筆數
    def num(s: str) -> float:
        s_clean = s.replace(",", "").strip()
        return float(s_clean) if s_clean not in ("", "--") else 0.0

    return {
        "date": _roc_to_iso(row[0]),
        # 成交量在櫃買中心新 API 為「成交仟股」，需乘上 1000 換算為股
        "volume": num(row[1]) * 1000.0,
        "open": num(row[3]),
        "high": num(row[4]),
        "low": num(row[5]),
        "close": num(row[6]),
    }


def _roc_to_iso(roc: str) -> str:
    """民國日期 '113/06/03' -> '2024-06-03'。"""
    parts = roc.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid ROC date format: {roc}")
    y, m, d = parts
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}"
