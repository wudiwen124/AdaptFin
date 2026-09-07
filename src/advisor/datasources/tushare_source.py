"""Tushare Pro 数据源（可选，需要 TUSHARE_TOKEN）。

MVP 覆盖：历史日 K（pro.daily）与估值（pro.daily_basic）；实时行情不支持。
token 缺失或未安装时按 DataSourceUnavailable 处理，不会阻塞 demo 链路。
"""

from __future__ import annotations

import os
from datetime import date

from advisor.datasources.base import BaseDataSource, DataSourceUnavailable
from advisor.schemas.common import Period, Symbol
from advisor.schemas.market import KLine, KLineBar, Valuation


class TushareDataSource(BaseDataSource):
    name = "tushare"

    @staticmethod
    def _import():
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise DataSourceUnavailable("缺少 TUSHARE_TOKEN", details=["请在 .env 中配置"])
        try:
            import tushare as ts  # noqa: PLC0415
        except ImportError as exc:
            raise DataSourceUnavailable("tushare 未安装（pip install -e '.[data]'）", details=[str(exc)]) from exc
        ts.set_token(token)
        return ts

    @staticmethod
    def _ts_code(symbol: Symbol) -> str:
        return f"{symbol.code}.{'SH' if symbol.exchange == 'sh' else 'SZ' if symbol.exchange == 'sz' else 'BJ'}"

    def kline(self, symbol: Symbol, period: Period = Period.DAILY, **kwargs) -> KLine:
        if period != Period.DAILY:
            raise DataSourceUnavailable("tushare MVP 仅支持日 K")
        ts = self._import()
        start = kwargs.get("start_date") or date(2023, 1, 1)
        end = kwargs.get("end_date") or date.today()
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        try:
            pro = ts.pro_api()
            df = pro.daily(
                ts_code=self._ts_code(symbol),
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        except Exception as exc:
            raise DataSourceUnavailable(f"tushare 日 K 异常: {exc}", details=[str(exc)]) from exc
        if df is None or df.empty:
            raise DataSourceUnavailable(f"tushare 日 K 为空: {symbol.code}")
        df = df.sort_values("trade_date")
        bars = [
            KLineBar(
                date=date(int(str(r["trade_date"])[:4]), int(str(r["trade_date"])[4:6]), int(str(r["trade_date"])[6:8])),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("vol") or 0),
            )
            for _, r in df.iterrows()
        ]
        return KLine(
            symbol=symbol,
            period=period,
            bars=bars,
            meta=self._meta(data_as_of=bars[-1].date.isoformat()),
        )

    def valuation(self, symbol: Symbol) -> Valuation:
        ts = self._import()
        try:
            pro = ts.pro_api()
            df = pro.daily_basic(
                ts_code=self._ts_code(symbol),
                start_date=date.today().strftime("%Y%m%d"),
                end_date=date.today().strftime("%Y%m%d"),
            )
        except Exception as exc:
            raise DataSourceUnavailable(f"tushare 估值异常: {exc}", details=[str(exc)]) from exc
        if df is None or df.empty:
            raise DataSourceUnavailable(f"tushare 估值为空: {symbol.code}")
        r = df.iloc[0]
        return Valuation(
            symbol=symbol,
            pe_ttm=float(r["pe_ttm"]) if r.get("pe_ttm") else None,
            pb=float(r["pb"]) if r.get("pb") else None,
            dividend_yield=float(r["dv_ttm"]) if r.get("dv_ttm") else None,
            meta=self._meta(data_as_of=date.today().isoformat()),
        )
