from datetime import date

from advisor.datasources.demo import DemoDataSource as DemoSource
from advisor.schemas.common import Symbol
from advisor.schemas.market import Quote


def _demo() -> DemoSource:
    return DemoSource()


def test_quote_fields_and_meta():
    source = _demo()
    quote = source.realtime_quote(Symbol.parse("600519"))
    assert isinstance(quote, Quote)
    assert quote.price > 0
    assert quote.meta.source == "demo"
    assert quote.meta.is_demo is True
    assert quote.meta.data_as_of
    assert "演示" in (quote.name or "")


def test_kline_consistent_ohlc_and_length():
    source = _demo()
    kline = source.kline(Symbol.parse("600519"), days=60)
    assert len(kline.bars) == 60
    for bar in kline.bars:
        assert bar.low <= min(bar.open, bar.close)
        assert bar.high >= max(bar.open, bar.close)
        assert bar.volume > 0
    assert kline.bars[-1].date <= date.today()


def test_kline_deterministic():
    source = _demo()
    sym = Symbol.parse("600519")
    a = source.kline(sym, days=30)
    b = source.kline(sym, days=30)
    assert [x.close for x in a.bars] == [x.close for x in b.bars]


def test_etf_and_stock_kinds():
    etf = Symbol.parse("510300")
    assert etf.kind == "etf"
    assert etf.exchange == "sh"
    stock = Symbol.parse("000001")
    assert stock.kind == "stock"
    assert stock.exchange == "sz"
