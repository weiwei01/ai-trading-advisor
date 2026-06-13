"""Obsidian 持股總表解析測試 — 用內嵌樣本，不依賴真實 vault。"""
from pathlib import Path

from app.market import obsidian

SAMPLE = """---
title: "證券持股總表 2026-06-09"
---

## 總覽

| 券商 | 筆數 |
|---|---:|
| 台新證券 | 2 |

## 台新證券明細（2 檔）

| 代號 | 股票 | 現價 | 成本均價 | 庫存股數 | 估算市值 |
|---:|---|---:|---:|---:|---:|
| 2330 | 台積電 | 2,305.00 | 2,146.05 | 500 | 1,152,500 |
| 1815 | 富喬 | 98.90 | 110.16 | 2,000 | 197,800 |

## 玉山證券明細（2 檔）

| 代號 | 股票 | 今價 | 成交均價 | 今餘股數 | 估算市值 |
|---:|---|---:|---:|---:|---:|
| 2330 | 台積電 | 2,305.00 | 641.45 | 3,674 | 8,468,570 |
| 9999 | 已出清 | 10.00 | 9.00 | 0 | 0 |

## 本次更新重點

- 不應被解析的內容
"""


def _write_vault(tmp_path: Path) -> Path:
    (tmp_path / "證券持股總表 2026-06-01.md").write_text("## 台新證券明細\n", encoding="utf-8")
    (tmp_path / "證券持股總表 2026-06-09.md").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "雜項.md").write_text("略過", encoding="utf-8")
    return tmp_path


def test_latest_file_picked_by_name(tmp_path):
    _write_vault(tmp_path)
    latest = obsidian.latest_holdings_file(tmp_path)
    assert latest is not None and latest.name == "證券持股總表 2026-06-09.md"


def test_parse_two_brokers(tmp_path):
    _write_vault(tmp_path)
    holdings, source = obsidian.load_holdings(tmp_path)
    assert source == "證券持股總表 2026-06-09.md"
    # 2330x2 + 1815；9999 股數 0 應被排除
    assert len(holdings) == 3
    symbols = {h.symbol for h in holdings}
    assert symbols == {"2330", "1815"}


def test_positions_summed_across_brokers(tmp_path):
    _write_vault(tmp_path)
    positions, _ = obsidian.load_positions(tmp_path)
    assert positions["2330"] == 500 + 3674   # 跨券商彙總
    assert positions["1815"] == 2000
    assert "9999" not in positions            # 已出清不納入


def test_missing_vault_returns_empty(tmp_path):
    holdings, source = obsidian.load_holdings(tmp_path / "不存在")
    assert holdings == [] and source is None


def test_cash_from_frontmatter(tmp_path):
    (tmp_path / "證券持股總表 2026-06-09.md").write_text(
        '---\ntitle: x\navailable_cash: 500,000\n---\n## 台新證券明細\n', encoding="utf-8"
    )
    cash, src = obsidian.load_cash(tmp_path)
    assert cash == 500000.0 and "frontmatter" in src


def test_cash_from_body_synonyms(tmp_path):
    (tmp_path / "證券持股總表 2026-06-09.md").write_text(
        "# t\n可動用資金：1,234,567\n", encoding="utf-8"
    )
    cash, _ = obsidian.load_cash(tmp_path)
    assert cash == 1234567.0


def test_cash_missing_returns_none(tmp_path):
    (tmp_path / "證券持股總表 2026-06-09.md").write_text("# t\n沒寫\n", encoding="utf-8")
    cash, src = obsidian.load_cash(tmp_path)
    assert cash is None and src is None
