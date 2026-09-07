"""行情与基本面数据模型（所有数据源统一输出此结构）。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from advisor.schemas.common import Period, Symbol


class SourceMeta(BaseModel):
    """数据出处：面试/审计层面要求每个数字都能回溯到“哪个源 + 什么时间”。"""

    source: str
    fetched_at: datetime
    data_as_of: datetime | str | None = None
    is_demo: bool = False
    degraded: bool = False
    note: str | None = None


class Quote(BaseModel):
    symbol: Symbol
    price: float = Field(gt=0)
    change_pct: float | None = None
    prev_close: float | None = None
    amount: float | None = None       # 成交额（元）
    name: str | None = None
    meta: SourceMeta


class KLineBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class KLine(BaseModel):
    symbol: Symbol
    period: Period = Period.DAILY
    bars: list[KLineBar]
    meta: SourceMeta

    def closes(self) -> list[float]:
        return [b.close for b in self.bars]


class IndexSnapshot(BaseModel):
    name: str
    code: str
    price: float
    change_pct: float | None = None
    meta: SourceMeta


class CompanyProfile(BaseModel):
    symbol: Symbol
    industry: str | None = None
    main_business: str | None = None
    market_cap: float | None = None   # 总市值（元）
    meta: SourceMeta


class FinancialSummary(BaseModel):
    symbol: Symbol
    report_period: str | None = None
    revenue_yoy: float | None = None
    net_profit_yoy: float | None = None
    roe: float | None = None          # 百分比数值，如 15.2 表示 15.2%
    gross_margin: float | None = None
    meta: SourceMeta


class Valuation(BaseModel):
    symbol: Symbol
    pe_ttm: float | None = None
    pb: float | None = None
    dividend_yield: float | None = None
    meta: SourceMeta


class NewsHeadline(BaseModel):
    title: str
    source: str
    published_at: str
    url: str | None = None
