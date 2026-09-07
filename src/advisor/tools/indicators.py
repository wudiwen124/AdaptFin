"""本地确定性技术指标：纯 Python 实现，LLM 不参与计算。

规则：指标必须能单测、可复算；数值路径上不允许模型心算。
"""

from __future__ import annotations

import math
import statistics

from pydantic import BaseModel, Field

from advisor.schemas.market import KLine


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return round(sum(values[-window:]) / window, 4)


def rsi_wilder(closes: list[float], period: int = 14) -> float | None:
    """Wilder RSI。数据不足时返回 None。"""
    if len(closes) <= period:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def annualized_volatility_pct(closes: list[float], periods_per_year: int = 252) -> float | None:
    if len(closes) < 2:
        return None
    returns = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    sd = statistics.stdev(returns) if len(returns) > 1 else 0.0
    return round(sd * math.sqrt(periods_per_year) * 100.0, 2)


def max_drawdown(closes: list[float]) -> float:
    """返回最大回撤（负值，如 -0.18 表示 18%）。"""
    peak = closes[0]
    mdd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        if peak > 0:
            mdd = min(mdd, price / peak - 1.0)
    return round(mdd, 4)


class TrendIndicators(BaseModel):
    symbol: str
    ma20: float | None = None
    ma60: float | None = None
    rsi14: float | None = None
    annualized_vol_pct: float | None = None
    max_drawdown: float | None = None
    n_bars: int = Field(default=0)
    as_of: str | None = None


def compute_trend_indicators(kline: KLine) -> TrendIndicators:
    closes = kline.closes()
    return TrendIndicators(
        symbol=str(kline.symbol),
        ma20=sma(closes, 20),
        ma60=sma(closes, 60),
        rsi14=rsi_wilder(closes, 14),
        annualized_vol_pct=annualized_volatility_pct(closes),
        max_drawdown=max_drawdown(closes) if closes else None,
        n_bars=len(closes),
        as_of=kline.bars[-1].date.isoformat() if kline.bars else None,
    )
