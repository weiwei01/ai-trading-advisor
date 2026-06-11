"""櫃買中心 (TPEx) API — 每日 K 棒歷史趨勢 (上櫃標的)。"""
from __future__ import annotations

import httpx
from typing import List

_BASE = "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php"


def fetch_otc_daily_candles(symbol: str, yyyymm: str) -> List[dict]:
    """抓取上櫃某月每日 K 棒。yyyymm 例如 '20240601'。
    
    回傳統一格式：{date, open, high, low, close, volume}。
    """
    # yyyymm -> 民國年/月，例如 20240601 -> 113/06
    y = int(yyyymm[:4])
    m = int(yyyymm[4:6])
    roc_year = y - 1911
    d_param = f"{roc_year}/{m:02d}"

    params = {"d": d_param, "stkno": symbol}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43.php"
    }
    resp = httpx.get(_BASE, params=params, headers=headers, timeout=10.0, follow_redirects=True)
    resp.raise_for_status()
    payload = resp.json()
    
    # 櫃買中心無資料時可能無 aaData 欄位
    if "aaData" not in payload:
        return []
        
    return [_parse_row(r) for r in payload.get("aaData", [])]


def _parse_row(row: List[str]) -> dict:
    # row 格式: 日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌價差, 成交筆數
    def num(s: str) -> float:
        s_clean = s.replace(",", "").strip()
        return float(s_clean) if s_clean not in ("", "--") else 0.0

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
    # 櫃買中心有時日期會是 '113/06/03'
    parts = roc.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid ROC date format: {roc}")
    y, m, d = parts
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}"
