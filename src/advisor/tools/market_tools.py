"""Function Calling 工具集（Market/Research 域）。

每个工具：pydantic args_schema + 中文 docstring；失败时返回 JSON {"error": ...}，
由上层 Agent 感知降级，而不是把异常直接抛给模型。
"""

from __future__ import annotations

import json
from datetime import date

from langchain_core.tools import Tool
from pydantic import BaseModel, Field

from advisor.datasources import DataSourceError, DataSourceRouter
from advisor.schemas.common import Period, Symbol
from advisor.schemas.market import NewsHeadline
from advisor.tools.indicators import compute_trend_indicators


def _ok(payload: BaseModel | list[BaseModel] | dict) -> str:
    if isinstance(payload, BaseModel):
        return payload.model_dump_json()
    if isinstance(payload, list):
        return json.dumps([p.model_dump(mode="json") for p in payload], ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def _err(exc: Exception) -> str:
    return json.dumps({"error": str(exc)}, ensure_ascii=False)


class SymbolArg(BaseModel):
    symbol: str = Field(description="6 位证券代码，如 600519 / 510300，可带 sh/sz 前缀")


class KlineArg(SymbolArg):
    start_date: str | None = Field(default=None, description="起始日期 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="截止日期 YYYY-MM-DD")
    limit: int = Field(default=180, ge=10, le=500, description="最多返回最近多少根 K 线")


class IndicatorsArg(SymbolArg):
    end_date: str | None = Field(default=None, description="截止日期 YYYY-MM-DD")


class NoArgs(BaseModel):
    pass


class MarketTools:
    def __init__(self, router: DataSourceRouter) -> None:
        self.router = router

    # ---- 工具实现（返回 JSON 字符串）----
    def get_realtime_quote(self, symbol: str) -> str:
        """获取 A 股个股/ETF 实时行情（最新价、涨跌幅、成交额、行情时间）。只返回事实，不含评价。"""
        try:
            return _ok(self.router.realtime_quote(Symbol.parse(symbol)))
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_daily_kline(self, symbol: str, start_date: str | None = None, end_date: str | None = None, limit: int = 180) -> str:
        """获取日 K 线（OHLCV），用于趋势/回撤分析。返回最多 limit 根。"""
        try:
            sym = Symbol.parse(symbol)
            kline = self.router.kline(
                sym,
                period=Period.DAILY,
                start_date=start_date or date(2023, 1, 1),
                end_date=end_date or date.today(),
            )
            if limit < len(kline.bars):
                kline = kline.model_copy(update={"bars": kline.bars[-limit:]})
            return _ok(kline)
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_technical_indicators(self, symbol: str, end_date: str | None = None) -> str:
        """本地确定性计算 MA20/MA60/RSI14/年化波动/最大回撤。不做预测，只给指标。"""
        try:
            sym = Symbol.parse(symbol)
            kline = self.router.kline(
                sym,
                period=Period.DAILY,
                start_date=date(2024, 1, 1),
                end_date=end_date or date.today(),
            )
            return _ok(compute_trend_indicators(kline))
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_financial_summary(self, symbol: str) -> str:
        """获取财务摘要（营收/净利同比、ROE、毛利率），带数据日期。"""
        try:
            return _ok(self.router.financial_summary(Symbol.parse(symbol)))
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_company_profile(self, symbol: str) -> str:
        """获取公司概况（行业/主营/市值）。"""
        try:
            return _ok(self.router.company_profile(Symbol.parse(symbol)))
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_valuation(self, symbol: str) -> str:
        """获取估值（PE-TTM/PB/股息率），带数据日期。"""
        try:
            return _ok(self.router.valuation(Symbol.parse(symbol)))
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_index_snapshot(self) -> str:
        """获取主要指数快照（上证/深证/沪深300/创业板指）。"""
        try:
            return _ok(self.router.index_snapshot())
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def get_recent_news(self, symbol: str, limit: int = 8) -> str:
        """获取最近公开新闻/公告标题列表（含来源与日期；MVP 为演示源）。"""
        try:
            items = self.router.news_headlines(Symbol.parse(symbol), limit=limit)
            return _ok(items if isinstance(items, list) else [items])
        except (DataSourceError, ValueError) as exc:
            return _err(exc)

    def as_tools(self) -> list[Tool]:
        tools = [
            Tool(name="get_realtime_quote", description=self.get_realtime_quote.__doc__, args_schema=SymbolArg, func=self.get_realtime_quote),
            Tool(name="get_daily_kline", description=self.get_daily_kline.__doc__, args_schema=KlineArg, func=self.get_daily_kline),
            Tool(name="get_technical_indicators", description=self.get_technical_indicators.__doc__, args_schema=IndicatorsArg, func=self.get_technical_indicators),
            Tool(name="get_financial_summary", description=self.get_financial_summary.__doc__, args_schema=SymbolArg, func=self.get_financial_summary),
            Tool(name="get_company_profile", description=self.get_company_profile.__doc__, args_schema=SymbolArg, func=self.get_company_profile),
            Tool(name="get_valuation", description=self.get_valuation.__doc__, args_schema=SymbolArg, func=self.get_valuation),
            Tool(name="get_index_snapshot", description=self.get_index_snapshot.__doc__, args_schema=NoArgs, func=self.get_index_snapshot),
            Tool(name="get_recent_news", description=self.get_recent_news.__doc__, args_schema=SymbolArg, func=self.get_recent_news),
        ]
        return tools


def build_market_tools(router: DataSourceRouter) -> list[Tool]:
    return MarketTools(router).as_tools()
