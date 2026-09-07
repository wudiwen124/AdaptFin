"""akshare 真实数据源适配（延迟导入，未安装时按不可用处理）。

MVP 覆盖：实时行情 / 日 K / 动态估值（来自行情快照）。
财务摘要等暂不支持 → DataNotSupported，由 router 交给下一来源。
"""

from __future__ import annotations

from datetime import date

from advisor.datasources.base import BaseDataSource, DataSourceUnavailable
from advisor.schemas.common import Period, Symbol
from advisor.schemas.market import FinancialSummary, KLine, KLineBar, NewsHeadline, Quote, Valuation


def _col(row, *candidates):
    for c in candidates:
        if c in row.index:
            return row[c]
    return None


def _find_col(df, *substrings):
    for col in df.columns:
        if any(s in str(col) for s in substrings):
            return col
    return None


class AkshareDataSource(BaseDataSource):
    name = "akshare"

    @staticmethod
    def _import_akshare():
        try:
            import akshare as ak  # noqa: PLC0415
        except ImportError as exc:
            raise DataSourceUnavailable("akshare 未安装（pip install -e '.[data]'）", details=[str(exc)]) from exc
        return ak

    def realtime_quote(self, symbol: Symbol) -> Quote:
        ak = self._import_akshare()
        try:
            if symbol.kind == "etf":
                df = ak.fund_etf_spot_em()
                code_col = "代码"
            else:
                df = ak.stock_zh_a_spot_em()
                code_col = "代码"
            code_mask = df[code_col].astype(str).str.zfill(6) == symbol.code
            row = df.loc[code_mask]
            if row.empty:
                raise DataSourceUnavailable(f"akshare 未找到 {symbol.code}")
            r = row.iloc[0]
            price = float(_col(r, "最新价", "最新"))
            if price is None or price <= 0:
                raise DataSourceUnavailable(f"akshare 返回异常行情: {symbol.code}")
            return Quote(
                symbol=symbol,
                price=price,
                change_pct=float(_col(r, "涨跌幅") or 0.0),
                prev_close=float(_col(r, "昨收") or 0.0) or None,
                amount=float(_col(r, "成交额") or 0.0) or None,
                name=_col(r, "名称"),
                meta=self._meta(data_as_of=date.today().isoformat()),
            )
        except DataSourceUnavailable:
            raise
        except Exception as exc:  # akshare/网络/字段变更全部按数据源不可用处理
            raise DataSourceUnavailable(f"akshare 行情接口异常: {exc}", details=[str(exc)]) from exc

    def kline(self, symbol: Symbol, period: Period = Period.DAILY, **kwargs) -> KLine:
        ak = self._import_akshare()
        start = kwargs.get("start_date") or date(2023, 1, 1)
        end = kwargs.get("end_date") or date.today()
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        period_map = {Period.DAILY: "daily", Period.WEEKLY: "weekly", Period.MONTHLY: "monthly"}
        try:
            if symbol.kind == "etf":
                df = ak.fund_etf_hist_em(
                    symbol=symbol.code,
                    period=period_map[period],
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
            else:
                df = ak.stock_zh_a_hist(
                    symbol=symbol.code,
                    period=period_map[period],
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
        except Exception as exc:
            raise DataSourceUnavailable(f"akshare K 线接口异常: {exc}", details=[str(exc)]) from exc
        if df is None or df.empty:
            raise DataSourceUnavailable(f"akshare K 线为空: {symbol.code}")
        bars = []
        for _, r in df.iterrows():
            bars.append(
                KLineBar(
                    date=date.fromisoformat(str(r["日期"])),
                    open=float(r["开盘"]),
                    high=float(r["最高"]),
                    low=float(r["最低"]),
                    close=float(r["收盘"]),
                    volume=float(r.get("成交量") or 0.0),
                )
            )
        return KLine(
            symbol=symbol,
            period=period,
            bars=bars,
            meta=self._meta(data_as_of=bars[-1].date.isoformat() if bars else None),
        )

    def valuation(self, symbol: Symbol) -> Valuation:
        ak = self._import_akshare()
        try:
            if symbol.kind == "etf":
                df = ak.fund_etf_spot_em()
            else:
                df = ak.stock_zh_a_spot_em()
            row = df.loc[df["代码"].astype(str).str.zfill(6) == symbol.code]
            if row.empty:
                raise DataSourceUnavailable(f"akshare 未找到 {symbol.code}")
            r = row.iloc[0]
            return Valuation(
                symbol=symbol,
                pe_ttm=float(_col(r, "市盈率-动态") or 0.0) or None,
                pb=float(_col(r, "市净率") or 0.0) or None,
                dividend_yield=None,  # 快照列不稳定，MVP 不取值
                meta=self._meta(data_as_of=date.today().isoformat()),
            )
        except DataSourceUnavailable:
            raise
        except Exception as exc:
            raise DataSourceUnavailable(f"akshare 估值接口异常: {exc}", details=[str(exc)]) from exc

    def financial_summary(self, symbol: Symbol) -> FinancialSummary:
        """真实财务（东财业绩报表）：最近有披露的季度，取同比/ROE/毛利率。"""
        ak = self._import_akshare()
        last_error: Exception | None = None
        for report_date in ("20260630", "20260331", "20251231", "20250930"):
            try:
                df = ak.stock_yjbb_em(date=report_date)
                row = df.loc[df["股票代码"].astype(str).str.zfill(6) == symbol.code]
                if row.empty:
                    continue
                r = row.iloc[0]
                rev_col = _find_col(df, "营业总收入-同比增长")
                profit_col = _find_col(df, "净利润-同比增长")
                roe_col = _find_col(df, "净资产收益率")
                gross_col = _find_col(df, "销售毛利率")
                return FinancialSummary(
                    symbol=symbol,
                    report_period=f"{report_date[:4]} 中报" if report_date[4:6] == "06" else report_date,
                    revenue_yoy=float(_col(r, rev_col) or 0.0) or None,
                    net_profit_yoy=float(_col(r, profit_col) or 0.0) or None,
                    roe=float(_col(r, roe_col) or 0.0) or None,
                    gross_margin=float(_col(r, gross_col) or 0.0) or None,
                    meta=self._meta(data_as_of=report_date),
                )
            except Exception as exc:
                last_error = exc
                continue
        raise DataSourceUnavailable(f"akshare 财务接口异常: {last_error}", details=[str(last_error)]) from last_error

    def news_headlines(self, symbol: Symbol, **kwargs) -> list[NewsHeadline]:
        """真实公告（东方财富个股公告），按公告日期倒序返回最近 limit 条。"""
        ak = self._import_akshare()
        limit = int(kwargs.get("limit", 8))
        try:
            df = ak.stock_individual_notice_report(
                security=symbol.code,
                begin_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
            )
        except Exception as exc:
            raise DataSourceUnavailable(f"akshare 公告接口异常: {exc}", details=[str(exc)]) from exc
        if df is None or df.empty:
            raise DataSourceUnavailable(f"akshare 公告为空: {symbol.code}")
        title_col = _find_col(df, "公告标题") or df.columns[2]
        time_col = _find_col(df, "公告日期") or df.columns[4]
        url_col = _find_col(df, "网址", "地址") or df.columns[5]
        rows = df.sort_values(by=time_col, ascending=False).head(limit)
        out = []
        for _, r in rows.iterrows():
            out.append(
                NewsHeadline(
                    title=str(r[title_col]),
                    source="东方财富公告",
                    published_at=str(r[time_col])[:10],
                    url=str(r.get(url_col, "")) if url_col in r.index else None,
                )
            )
        return out
