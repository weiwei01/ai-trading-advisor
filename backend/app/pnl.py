"""損益計算 — FIFO 配對，成本實扣手續費與證交稅。

原則：寧願多算一點成本，也不要一個沒扣費用、自欺欺人的漂亮損益。
- FIFO：每一筆賣出配到最早的買進，逐筆算已實現損益。
- 未實現：尚未賣出的部位用即時價格估算。
- 費用：每筆都扣實際買賣手續費；賣出再扣證交稅，ETF 與個股稅率分開。
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List

from app.schemas import SecurityType

# --- 費率設定（可依券商折讓調整）---
BROKERAGE_RATE = 0.001425        # 手續費 0.1425%（買賣皆收）
BROKERAGE_DISCOUNT = 1.0         # 折讓倍率，例如 6 折 = 0.6
MIN_BROKERAGE = 20.0             # 單筆最低手續費（元）
TAX_RATE_STOCK = 0.003           # 個股證交稅 0.3%（僅賣出收）
TAX_RATE_ETF = 0.001             # ETF 證交稅 0.1%（僅賣出收）


def brokerage_fee(amount: float) -> float:
    """買或賣的手續費，套用折讓並取單筆最低值。"""
    fee = amount * BROKERAGE_RATE * BROKERAGE_DISCOUNT
    return max(fee, MIN_BROKERAGE) if amount > 0 else 0.0


def transaction_tax(amount: float, sec_type: SecurityType) -> float:
    """證交稅，僅賣出時收取，ETF 與個股分開。"""
    rate = TAX_RATE_ETF if sec_type == SecurityType.ETF else TAX_RATE_STOCK
    return amount * rate


@dataclass
class Fill:
    """一筆實際成交。"""

    symbol: str
    side: str            # "buy" | "sell"
    price: float
    quantity: int
    sec_type: SecurityType = SecurityType.STOCK
    date: str = ""


@dataclass
class _Lot:
    quantity: int
    price: float
    buy_fee_per_share: float   # 該批買進手續費攤到每股
    buy_date: str = ""


@dataclass
class RealizedTrade:
    symbol: str
    quantity: int
    buy_price: float
    sell_price: float
    cost: float          # 含買進手續費
    proceeds: float      # 扣賣出手續費與證交稅後的淨收入
    pnl: float
    buy_date: str = ""
    sell_date: str = ""


@dataclass
class PositionPnL:
    symbol: str
    quantity: int
    avg_cost: float          # 含手續費的每股平均成本
    market_price: float
    market_value: float
    unrealized_pnl: float


@dataclass
class PnLReport:
    realized: List[RealizedTrade] = field(default_factory=list)
    positions: List[PositionPnL] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


def compute_pnl(fills: List[Fill], market_prices: Dict[str, float]) -> PnLReport:
    """以 FIFO 配對計算已實現損益，並用市價估算未實現損益。"""
    lots: Dict[str, Deque[_Lot]] = defaultdict(deque)
    sec_types: Dict[str, SecurityType] = {}
    report = PnLReport()

    for f in fills:
        sec_types[f.symbol] = f.sec_type
        gross = f.price * f.quantity

        if f.side == "buy":
            fee = brokerage_fee(gross)
            lots[f.symbol].append(
                _Lot(quantity=f.quantity, price=f.price, buy_fee_per_share=fee / f.quantity, buy_date=f.date)
            )
        elif f.side == "sell":
            remaining = f.quantity
            sell_fee = brokerage_fee(gross)
            tax = transaction_tax(gross, f.sec_type)
            # 賣出端費用依股數比例攤到每一筆配對
            while remaining > 0 and lots[f.symbol]:
                lot = lots[f.symbol][0]
                matched = min(remaining, lot.quantity)
                portion = matched / f.quantity

                buy_cost = lot.price * matched + lot.buy_fee_per_share * matched
                proceeds = f.price * matched - (sell_fee + tax) * portion
                report.realized.append(
                    RealizedTrade(
                        symbol=f.symbol,
                        quantity=matched,
                        buy_price=lot.price,
                        sell_price=f.price,
                        cost=buy_cost,
                        proceeds=proceeds,
                        pnl=proceeds - buy_cost,
                        buy_date=lot.buy_date,
                        sell_date=f.date,
                    )
                )
                lot.quantity -= matched
                remaining -= matched
                if lot.quantity == 0:
                    lots[f.symbol].popleft()
            if remaining > 0:
                raise ValueError(f"{f.symbol} 賣出股數超過持有部位（多 {remaining} 股）")
        else:
            raise ValueError(f"未知交易方向：{f.side}")

    report.realized_pnl = sum(t.pnl for t in report.realized)

    # 未實現：剩餘 lots 用市價估
    for symbol, lot_q in lots.items():
        qty = sum(l.quantity for l in lot_q)
        if qty == 0:
            continue
        total_cost = sum(l.price * l.quantity + l.buy_fee_per_share * l.quantity for l in lot_q)
        avg_cost = total_cost / qty
        mkt = market_prices.get(symbol, 0.0)
        mv = mkt * qty
        pos = PositionPnL(
            symbol=symbol,
            quantity=qty,
            avg_cost=avg_cost,
            market_price=mkt,
            market_value=mv,
            unrealized_pnl=mv - total_cost,
        )
        report.positions.append(pos)

    report.unrealized_pnl = sum(p.unrealized_pnl for p in report.positions)
    return report
