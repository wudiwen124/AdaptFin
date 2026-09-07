"""数据源抽象与路由：统一入口 `build_default_router()` / `DataSourceRouter`。"""

from __future__ import annotations

import time
from typing import Any, Sequence

from pydantic import BaseModel

from advisor.config import Settings, load_settings
from advisor.datasources.base import (
    BaseDataSource,
    DataNotSupported,
    DataSourceError,
    DataSourceUnavailable,
)
from advisor.datasources.cache import TTLCache, cache_key
from advisor.schemas.market import SourceMeta


class DataSourceRouter:
    """按配置优先级调用数据源，统一缓存/重试/降级语义。

    - 某数据源抛 DataNotSupported → 跳过不重试；
    - 其余异常（含 DataSourceUnavailable）→ 按 max_retries 退避重试；
    - 前序来源全部失败后由后续来源（通常是 demo）兜底 → degraded=True；
    - 成功结果按方法级 TTL 缓存。
    """

    def __init__(
        self,
        sources: Sequence[BaseDataSource],
        *,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.4,
        ttl: dict[str, float] | None = None,
    ) -> None:
        if not sources:
            raise ValueError("至少需要一个数据源")
        self.sources = list(sources)
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._ttl = {"realtime_quote": 60, "kline": 86400, "financial_summary": 86400, **(ttl or {})}
        self._cache = TTLCache()

    # ---- 对外方法 ----
    def realtime_quote(self, symbol) -> Any:
        return self._call("realtime_quote", symbol, ttl_seconds=self._ttl["realtime_quote"])

    def kline(self, symbol, **kwargs: Any) -> Any:
        ttl = kwargs.pop("cache_ttl", self._ttl.get("kline", 86400))
        return self._call("kline", symbol, ttl_seconds=ttl, **kwargs)

    def company_profile(self, symbol) -> Any:
        return self._call("company_profile", symbol, ttl_seconds=self._ttl.get("financial_summary", 86400))

    def financial_summary(self, symbol) -> Any:
        return self._call("financial_summary", symbol, ttl_seconds=self._ttl.get("financial_summary", 86400))

    def valuation(self, symbol) -> Any:
        return self._call("valuation", symbol, ttl_seconds=self._ttl.get("financial_summary", 86400))

    def index_snapshot(self) -> Any:
        return self._call("index_snapshot", ttl_seconds=self._ttl.get("realtime_quote", 60))

    def news_headlines(self, symbol, limit: int = 10) -> Any:
        return self._call(
            "news_headlines",
            symbol,
            limit=limit,
            ttl_seconds=self._ttl.get("financial_summary", 86400),
        )

    # ---- 内部 ----
    def _call(self, method: str, *args: Any, ttl_seconds: float, **kwargs: Any) -> Any:
        key = cache_key(method, self._freeze(args), self._freeze(kwargs))
        if (hit := self._cache.get(key)) is not None:
            return hit

        failures: list[str] = []
        result = None
        degraded = False
        for source in self.sources:
            fn = getattr(source, method, None)
            if fn is None:
                failures.append(f"{source.name}: 未实现 {method}")
                continue
            for attempt in range(self.max_retries + 1):
                try:
                    result = fn(*args, **kwargs)
                except DataNotSupported as exc:
                    failures.append(f"{source.name}: {exc}")
                    result = None
                    break
                except Exception as exc:  # 含 DataSourceUnavailable / 网络异常
                    if attempt < self.max_retries:
                        time.sleep(self.retry_backoff_seconds * (attempt + 1))
                        continue
                    failures.append(f"{source.name}: {exc}")
                    result = None
                    break
                else:
                    degraded = bool(failures) and result is not None
                    break
            if result is not None:
                break

        if result is None:
            raise DataSourceUnavailable(
                f"全部数据源不可用（{method}）",
                details=failures,
            )

        result = self._mark_degraded(result, degraded=degraded, failures=failures)
        self._cache.set(key, result, ttl=ttl_seconds)
        return result

    @staticmethod
    def _freeze(args: tuple[Any, ...]) -> list[Any]:
        frozen = []
        for arg in args:
            if isinstance(arg, BaseModel):
                frozen.append(arg.model_dump(mode="json"))
            else:
                frozen.append(arg)
        return frozen

    @staticmethod
    def _mark_degraded(result: Any, *, degraded: bool, failures: list[str]) -> Any:
        if not hasattr(result, "meta") or not isinstance(result.meta, SourceMeta):
            return result
        note = None
        if failures:
            note = f"来源链回退: {' → '.join(failures)}"
        meta = result.meta.model_copy(
            update={"degraded": degraded or result.meta.degraded, "note": note or result.meta.note}
        )
        return result.model_copy(update={"meta": meta})


class DataSourceRegistry:
    """按名字实例化数据源；未知名字在启动即报错（fail-fast）。"""

    def __init__(self) -> None:
        # 延迟导入类定义避免未安装第三方包时 import 失败
        from advisor.datasources.akshare_source import AkshareDataSource
        from advisor.datasources.baostock_source import BaoStockDataSource
        from advisor.datasources.demo import DemoDataSource
        from advisor.datasources.tushare_source import TushareDataSource

        self._classes: dict[str, type[BaseDataSource]] = {
            cls.name: cls
            for cls in (AkshareDataSource, BaoStockDataSource, TushareDataSource, DemoDataSource)
        }

    def available_names(self) -> list[str]:
        return sorted(self._classes)

    def build(self, name: str) -> BaseDataSource:
        cls = self._classes.get(name)
        if cls is None:
            raise ValueError(f"未知数据源 {name!r}，可选: {', '.join(self.available_names())}")
        return cls()


def build_default_router(settings: Settings | None = None) -> DataSourceRouter:
    """按 settings.data.sources_priority 建 router；demo 自动追加到末尾兜底。"""
    settings = settings or load_settings()
    registry = DataSourceRegistry()
    names = list(settings.data.sources_priority)
    if "demo" not in names:
        names.append("demo")
    sources = [registry.build(name) for name in names]
    return DataSourceRouter(
        sources,
        max_retries=settings.data.max_retries,
        retry_backoff_seconds=settings.data.retry_backoff_seconds,
        ttl={
            "realtime_quote": float(settings.data.quote_ttl_seconds),
            "kline": float(settings.data.kline_ttl_seconds),
            "financial_summary": float(settings.data.financial_ttl_seconds),
        },
    )


__all__ = [
    "BaseDataSource",
    "DataNotSupported",
    "DataSourceError",
    "DataSourceRegistry",
    "DataSourceRouter",
    "DataSourceUnavailable",
    "TTLCache",
    "build_default_router",
]
