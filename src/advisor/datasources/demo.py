"""Demo 数据源：确定性生成，永不联网。面试/离线演示的兜底。"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from advisor.datasources.base import BaseDataSource
from advisor.schemas.common import Period, Symbol
from advisor.schemas.market import (
    CompanyProfile,
    FinancialSummary,
    IndexSnapshot,
    KLine,
    KLineBar,
    NewsHeadline,
    Quote,
    Valuation,
)


DEMO_NAMES = {
    "600519": "贵州茅台(演示)",
    "601318": "中国平安(演示)",
    "000001": "平安银行(演示)",
    "300750": "宁德时代(演示)",
    "510300": "沪深300ETF(演示)",
    "159915": "创业板ETF(演示)",
}

DEMO_INDEXES = [
    ("上证指数", "000001"),
    ("深证成指", "399001"),
    ("沪深300", "000300"),
    ("创业板指", "399006"),
]

NEWS_TEMPLATES = [
    "{name}：公司发布中期经营情况说明",
    "{name}：机构调研记录更新，关注主营业务进展",
    "行业资讯：{industry}板块成交活跃度上升",
    "{name}：投资者关系活动记录表披露",
    "宏观观察：市场资金面维持平稳（演示资讯）",
]


def _seed_for(symbol: Symbol) -> int:
    digest = hashlib.sha256(symbol.code.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _business_day_sequence(end: date, count: int) -> list[date]:
    """从 end 往前取 count 个工作日（简单跳过周末）。"""
    days: list[date] = []
    cur = end
    while len(days) < count:
        if cur.weekday() < 5:
            days.append(cur)
        cur -= timedelta(days=1)
    return list(reversed(days))


class DemoDataSource(BaseDataSource):
    name = "demo"
    is_demo = True

    def _base_price(self, symbol: Symbol) -> float:
        rng = random.Random(_seed_for(symbol))
        return round(rng.uniform(3.0, 280.0), 2)

    def realtime_quote(self, symbol: Symbol) -> Quote:
        rng = random.Random(_seed_for(symbol) ^ int(date.today().toordinal()))
        price = round(self._base_price(symbol) * rng.uniform(0.92, 1.12), 2)
        change_pct = round(rng.uniform(-6.5, 6.5), 2)
        prev_close = round(price / (1 + change_pct / 100), 2)
        amount = round(rng.uniform(2e8, 9e9), 2)
        return Quote(
            symbol=symbol,
            price=price,
            change_pct=change_pct,
            prev_close=prev_close,
            amount=amount,
            name=DEMO_NAMES.get(symbol.code, f"演示标的{symbol.code}"),
            meta=self._meta(data_as_of=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

    def kline(self, symbol: Symbol, period: Period = Period.DAILY, **kwargs) -> KLine:
        days = kwargs.get("days", 180)
        end = kwargs.get("end_date")
        if isinstance(end, str):
            end = date.fromisoformat(end)
        end = end or date.today()
        dates = _business_day_sequence(end, days)
        rng = random.Random(_seed_for(symbol))
        price = self._base_price(symbol) * rng.uniform(0.7, 0.9)
        bars: list[KLineBar] = []
        for d in dates:
            drift = rng.uniform(-0.018, 0.018)
            price = max(0.5, price * (1 + drift))
            o = price * (1 + rng.uniform(-0.008, 0.008))
            h = max(o, price) * (1 + rng.uniform(0.0, 0.012))
            l = min(o, price) * (1 - rng.uniform(0.0, 0.012))
            bars.append(
                KLineBar(
                    date=d,
                    open=round(o, 2),
                    high=round(h, 2),
                    low=round(l, 2),
                    close=round(price, 2),
                    volume=round(rng.uniform(1e6, 8e7), 0),
                )
            )
        return KLine(
            symbol=symbol,
            period=period,
            bars=bars,
            meta=self._meta(data_as_of=bars[-1].date.isoformat() if bars else None),
        )

    def company_profile(self, symbol: Symbol) -> CompanyProfile:
        industries = ["食品饮料(演示)", "金融(演示)", "新能源(演示)", "信息技术(演示)"]
        rng = random.Random(_seed_for(symbol))
        return CompanyProfile(
            symbol=symbol,
            industry=industries[rng.randrange(len(industries))],
            main_business="演示数据：主营描述待接入真实数据源",
            market_cap=round(rng.uniform(2e10, 2e12), 0),
            meta=self._meta(data_as_of=date.today().isoformat()),
        )

    def financial_summary(self, symbol: Symbol) -> FinancialSummary:
        rng = random.Random(_seed_for(symbol) ^ 0x51)
        return FinancialSummary(
            symbol=symbol,
            report_period="2026Q2(演示)",
            revenue_yoy=round(rng.uniform(-20, 45), 2),
            net_profit_yoy=round(rng.uniform(-35, 60), 2),
            roe=round(rng.uniform(2, 28), 2),
            gross_margin=round(rng.uniform(8, 70), 2),
            meta=self._meta(data_as_of=date.today().isoformat()),
        )

    def valuation(self, symbol: Symbol) -> Valuation:
        rng = random.Random(_seed_for(symbol) ^ 0x22)
        return Valuation(
            symbol=symbol,
            pe_ttm=round(rng.uniform(8, 60), 2),
            pb=round(rng.uniform(0.8, 12), 2),
            dividend_yield=round(rng.uniform(0.0, 6.0), 2),
            meta=self._meta(data_as_of=date.today().isoformat()),
        )

    def index_snapshot(self) -> list[IndexSnapshot]:
        rng = random.Random(date.today().toordinal())
        out = []
        for name, code in DEMO_INDEXES:
            out.append(
                IndexSnapshot(
                    name=name,
                    code=code,
                    price=round(rng.uniform(1500, 4200), 2),
                    change_pct=round(rng.uniform(-2, 2), 2),
                    meta=self._meta(data_as_of=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
            )
        return out

    def news_headlines(self, symbol: Symbol, **kwargs) -> list[NewsHeadline]:
        rng = random.Random(_seed_for(symbol) ^ 0x77)
        limit = int(kwargs.get("limit", 10))
        out = []
        for i in range(min(limit, len(NEWS_TEMPLATES))):
            idx = (i + rng.randrange(len(NEWS_TEMPLATES))) % len(NEWS_TEMPLATES)
            title = NEWS_TEMPLATES[idx].format(name=DEMO_NAMES.get(symbol.code, symbol.code), industry="行业")
            out.append(
                NewsHeadline(
                    title=title,
                    source="demo",
                    published_at=date.today().isoformat(),
                    url=None,
                )
            )
        return out
