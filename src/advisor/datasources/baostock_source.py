"""BaoStock 数据源（历史日/周/月 K，无实时行情）。

BaoStock 登录为进程级会话：每个线程首次调用时 login，进程退出无需显式 logout。
"""

from __future__ import annotations

import threading
from datetime import date

from advisor.datasources.base import BaseDataSource, DataSourceUnavailable
from advisor.schemas.common import Period, Symbol
from advisor.schemas.market import KLine, KLineBar

_bs_lock = threading.Lock()
_bs_login_state: dict[int, bool] = {}


class BaoStockDataSource(BaseDataSource):
    name = "baostock"

    @staticmethod
    def _import():
        try:
            import baostock as bs  # noqa: PLC0415
        except ImportError as exc:
            raise DataSourceUnavailable("baostock 未安装（pip install -e '.[data]'）", details=[str(exc)]) from exc
        return bs

    @classmethod
    def _ensure_login(cls, bs) -> None:
        tid = threading.get_ident()
        with _bs_lock:
            if not _bs_login_state.get(tid):
                lg = bs.login()
                if lg.error_code != "0":
                    raise DataSourceUnavailable(f"baostock 登录失败: {lg.error_msg}", details=[lg.error_code])
                _bs_login_state[tid] = True

    def kline(self, symbol: Symbol, period: Period = Period.DAILY, **kwargs) -> KLine:
        bs = self._import()
        self._ensure_login(bs)
        start = kwargs.get("start_date") or date(2023, 1, 1)
        end = kwargs.get("end_date") or date.today()
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        fields = "date,code,open,high,low,close,volume,amount"
        frequency = {Period.DAILY: "d", Period.WEEKLY: "w", Period.MONTHLY: "m"}[period]
        try:
            rs = bs.query_history_k_data_plus(
                symbol.akshare_symbol.upper(),
                fields,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                frequency=frequency,
                adjustflag="2",  # 前复权
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
        except Exception as exc:
            raise DataSourceUnavailable(f"baostock K 线异常: {exc}", details=[str(exc)]) from exc
        if not rows:
            raise DataSourceUnavailable(f"baostock K 线为空: {symbol.code}")
        bars = [
            KLineBar(
                date=date.fromisoformat(r[0]),
                open=float(r[2]),
                high=float(r[3]),
                low=float(r[4]),
                close=float(r[5]),
                volume=float(r[6] or 0),
            )
            for r in rows
        ]
        return KLine(
            symbol=symbol,
            period=period,
            bars=bars,
            meta=self._meta(data_as_of=bars[-1].date.isoformat()),
        )
