"""從 Obsidian 持股總表讀取真實持股。

對應使用者的 Obsidian vault（沿用 stock_dashboard 專案的解析方式）：
- 路徑：03-Investing/持股管理/總表/ 下的「證券持股總表 YYYY-MM-DD.md」，取檔名最新者。
- 解析「## 台新證券明細」「## 玉山證券明細」兩區塊的表格：
  | 代號 | 股票 | 現價 | 成本均價 | 庫存股數 | ...
  col0=代號(4~5碼), col1=名稱, col3=成本均價, col4=庫存股數
- 跨券商以代號彙總股數，已出清（股數<=0）不納入。

這層只讀取、不寫入；定位仍是決策輔助，持股以券商 App 為準。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DEFAULT_VAULT = (
    Path.home()
    / "Library/Mobile Documents/iCloud~md~obsidian/Documents"
    / "IcloudVault/03-Investing/持股管理/總表"
)

_SECTIONS = ["台新證券明細", "玉山證券明細"]
_CODE_RE = re.compile(r"^\d{4,5}$")


@dataclass
class Holding:
    symbol: str
    name: str
    shares: int
    cost: float       # 成本均價
    broker: str


def vault_dir() -> Path:
    """可用環境變數 OBSIDIAN_VAULT_DIR 覆寫總表資料夾路徑。"""
    override = os.getenv("OBSIDIAN_VAULT_DIR")
    return Path(override) if override else _DEFAULT_VAULT


def _parse_num(s: str) -> float:
    if not s:
        return 0.0
    cleaned = s.replace(",", "").replace("*", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_section(text: str, section_title: str, broker: str) -> List[Holding]:
    start = text.find(f"## {section_title}")
    if start == -1:
        return []
    end = text.find("\n## ", start + 3)
    section = text[start:] if end == -1 else text[start:end]

    out: List[Holding] = []
    for line in section.splitlines():
        trimmed = line.strip()
        if not trimmed.startswith("|"):
            continue
        cols = [c.strip() for c in trimmed.split("|") if c.strip()]
        if len(cols) < 5 or not _CODE_RE.match(cols[0]):
            continue
        shares = int(_parse_num(cols[4]))
        if shares <= 0:           # 已出清不納入
            continue
        out.append(
            Holding(symbol=cols[0], name=cols[1], shares=shares,
                    cost=_parse_num(cols[3]), broker=broker)
        )
    return out


def latest_holdings_file(directory: Optional[Path] = None) -> Optional[Path]:
    directory = directory or vault_dir()
    try:
        files = sorted(
            f for f in directory.iterdir()
            if f.name.startswith("證券持股總表") and f.suffix == ".md"
        )
    except OSError:
        return None
    return files[-1] if files else None


def load_holdings(directory: Optional[Path] = None) -> Tuple[List[Holding], Optional[str]]:
    """讀取最新總表，回傳 (逐筆持股, 來源檔名)。檔案不存在時回 ([], None)。"""
    path = latest_holdings_file(directory)
    if path is None:
        return [], None
    text = path.read_text(encoding="utf-8")
    holdings: List[Holding] = []
    for title, broker in zip(_SECTIONS, ["台新", "玉山"]):
        holdings += _parse_section(text, title, broker)
    return holdings, path.name


def load_positions(directory: Optional[Path] = None) -> Tuple[Dict[str, int], Optional[str]]:
    """跨券商彙總成 {代號: 總股數}，供 MarketContext.positions 使用。"""
    holdings, source = load_holdings(directory)
    positions: Dict[str, int] = {}
    for h in holdings:
        positions[h.symbol] = positions.get(h.symbol, 0) + h.shares
    return positions, source
