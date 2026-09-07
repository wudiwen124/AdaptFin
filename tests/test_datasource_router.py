from advisor.datasources import DataSourceRouter, DataSourceUnavailable
from advisor.datasources.base import BaseDataSource, DataNotSupported
from advisor.datasources.demo import DemoDataSource
from advisor.schemas.common import Symbol
from advisor.schemas.market import Quote


class AlwaysFail(BaseDataSource):
    name = "always_fail"

    def realtime_quote(self, symbol):
        raise DataSourceUnavailable("模拟接口挂了")


class CountingSource(BaseDataSource):
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def realtime_quote(self, symbol):
        self.calls += 1
        return Quote(symbol=symbol, price=10.0, meta=self._meta(data_as_of="2026-09-07"))


def test_demo_only_no_degradation():
    router = DataSourceRouter([DemoDataSource()], max_retries=0)
    q = router.realtime_quote(Symbol.parse("600519"))
    assert q.meta.degraded is False
    assert q.meta.source == "demo"


def test_fallback_marks_degraded():
    router = DataSourceRouter([AlwaysFail(), DemoDataSource()], max_retries=0)
    q = router.realtime_quote(Symbol.parse("600519"))
    assert q.meta.degraded is True
    assert "回退" in (q.meta.note or "")


def test_all_fail_raises_unavailable():
    router = DataSourceRouter([AlwaysFail()], max_retries=0)
    try:
        router.realtime_quote(Symbol.parse("600519"))
    except DataSourceUnavailable as exc:
        assert "全部数据源不可用" in str(exc)
        assert exc.details
    else:
        raise AssertionError("应当抛出 DataSourceUnavailable")


def test_not_supported_skips_to_next():
    class NoValuation(BaseDataSource):
        name = "no_valuation"

    router = DataSourceRouter([NoValuation(), DemoDataSource()], max_retries=0)
    v = router.valuation(Symbol.parse("600519"))
    assert v.meta.source == "demo"
    assert v.meta.degraded is True  # 能力缺失也算来源链回退


def test_cache_prevents_second_fetch():
    source = CountingSource()
    router = DataSourceRouter([source], max_retries=0)
    sym = Symbol.parse("600519")
    router.realtime_quote(sym)
    router.realtime_quote(sym)
    assert source.calls == 1


def test_registry_available_names():
    from advisor.datasources import DataSourceRegistry

    names = DataSourceRegistry().available_names()
    assert {"demo", "akshare", "baostock", "tushare"} <= set(names)
