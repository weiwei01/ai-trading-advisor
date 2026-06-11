"""規則型 advisor — 不呼叫 LLM、不燒 Token 的另一個 TradingAdvisor 實作。

用途：用真實日 K 跑出「有成交、有勝率/期望值」的回測，先確認
決策→風控→損益整條鏈路正確，再換上 Codex。

策略（皆為純函式可測）：
- 進場：短均線向上穿越長均線（黃金交叉）或收盤突破近 N 日高點。
- 出場：短均線向下跌破長均線（死亡交叉）或收盤跌破近 N 日低點。
信心分數由訊號強度（均線乖離）粗略換算，僅供風控門檻參考。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.advisor.base import MarketContext, TradingAdvisor
from app.schemas import Action, Proposal, ProposalBatch


@dataclass
class RuleConfig:
    short_window: int = 5
    long_window: int = 20
    breakout_window: int = 20
    position_size: int = 1000      # 每次進場股數
    max_confidence: float = 0.9


def sma(values: List[float], window: int) -> Optional[float]:
    """簡單移動平均；資料不足回 None（純函式）。"""
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def _closes(candles: List[dict]) -> List[float]:
    return [c["close"] for c in candles]


def evaluate_symbol(
    symbol: str,
    candles: List[dict],
    held: int,
    cfg: RuleConfig,
) -> Optional[Proposal]:
    """對單一標的依規則產生提案，無訊號回 None（純函式）。"""
    closes = _closes(candles)
    if len(closes) < cfg.long_window + 1:
        return None

    short_now = sma(closes, cfg.short_window)
    long_now = sma(closes, cfg.long_window)
    short_prev = sma(closes[:-1], cfg.short_window)
    long_prev = sma(closes[:-1], cfg.long_window)
    if None in (short_now, long_now, short_prev, long_prev):
        return None

    price = closes[-1]
    recent = closes[-(cfg.breakout_window + 1):-1]   # 不含當日
    prior_high = max(recent) if recent else price
    prior_low = min(recent) if recent else price

    golden_cross = short_prev <= long_prev and short_now > long_now
    breakout_up = price > prior_high
    death_cross = short_prev >= long_prev and short_now < long_now
    breakdown = price < prior_low

    spread = abs(short_now - long_now) / long_now if long_now else 0.0
    confidence = round(min(cfg.max_confidence, 0.5 + spread * 10), 2)

    if held <= 0 and (golden_cross or breakout_up):
        reason = "黃金交叉（5 穿越 20 日均線）" if golden_cross else f"突破近 {cfg.breakout_window} 日高 {prior_high:.2f}"
        return Proposal(
            symbol=symbol, action=Action.BUY, price=price,
            quantity=cfg.position_size, confidence=confidence,
            reason=reason,
            risk_note=f"跌破 20 日均線或近 {cfg.breakout_window} 日低 {prior_low:.2f} 應出場",
            stop_loss=round(prior_low, 2),
        )

    if held > 0 and (death_cross or breakdown):
        reason = "死亡交叉（5 跌破 20 日均線）" if death_cross else f"跌破近 {cfg.breakout_window} 日低 {prior_low:.2f}"
        return Proposal(
            symbol=symbol, action=Action.SELL, price=price,
            quantity=min(held, cfg.position_size), confidence=confidence,
            reason=reason,
            risk_note="出場後若再站回均線可重新評估進場",
        )

    return None


class RuleBasedAdvisor(TradingAdvisor):
    def __init__(self, config: Optional[RuleConfig] = None) -> None:
        self.cfg = config or RuleConfig()

    def propose(self, context: MarketContext) -> ProposalBatch:
        proposals: List[Proposal] = []
        for symbol, candles in context.candles.items():
            held = context.positions.get(symbol, 0)
            p = evaluate_symbol(symbol, candles, held, self.cfg)
            if p is not None:
                proposals.append(p)
        return ProposalBatch(proposals=proposals, model_note="rule-based")
