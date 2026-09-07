"""数据源协议与异常体系。"""

from __future__ import annotations

from abc import ABC
from datetime import datetime, timezone

from advisor.schemas.market import SourceMeta


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataSourceError(RuntimeError):
    pass


class DataNotSupported(DataSourceError):
    """该数据源不支持此能力（不重试，直接尝试下一来源）。"""


class DataSourceUnavailable(DataSourceError):
    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class BaseDataSource(ABC):
    """统一数据源接口。MVP 契约：每个方法返回对应 pydantic 模型并自带 SourceMeta。

    默认实现为“不支持”，具体源按能力覆盖：
    - DemoDataSource：全能力（兜底）；
    - AkshareDataSource：实时行情 / 日 K / 估值；
    - BaoStockDataSource：历史 K（无实时）；
    - TushareDataSource：历史 K / 估值（需 token，集成测试）。
    """

    name: str = "base"
    is_demo: bool = False

    def realtime_quote(self, symbol):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持实时行情")

    def kline(self, symbol, **kwargs):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持 K 线")

    def company_profile(self, symbol):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持公司概况")

    def financial_summary(self, symbol):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持财务摘要")

    def valuation(self, symbol):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持估值数据")

    def index_snapshot(self):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持指数快照")

    def news_headlines(self, symbol):  # noqa: D102
        raise DataNotSupported(f"{self.name} 不支持新闻")

    def _meta(self, *, data_as_of=None, degraded: bool = False, note: str | None = None) -> SourceMeta:
        return SourceMeta(
            source=self.name,
            fetched_at=utcnow(),
            data_as_of=data_as_of,
            is_demo=self.is_demo,
            degraded=degraded,
            note=note,
        )
