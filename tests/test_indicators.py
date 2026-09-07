import pytest

from advisor.datasources.demo import DemoDataSource
from advisor.schemas.common import Symbol
from advisor.tools.indicators import (
    annualized_volatility_pct,
    compute_trend_indicators,
    max_drawdown,
    rsi_wilder,
    sma,
)


def test_sma_last_window():
    values = [float(i) for i in range(1, 11)]
    assert sma(values, 3) == 9.0
    assert sma(values, 99) is None


def test_rsi_bounds():
    rising = [100.0 + i for i in range(30)]
    falling = [200.0 - i for i in range(30)]
    assert rsi_wilder(rising) == 100.0
    assert rsi_wilder(falling) == 0.0
    assert rsi_wilder([1.0, 2.0]) is None


def test_max_drawdown():
    closes = [100.0, 120.0, 90.0, 80.0, 110.0]
    assert max_drawdown(closes) == pytest.approx(80.0 / 120.0 - 1.0, abs=1e-4)


def test_volatility():
    assert annualized_volatility_pct([100.0]) is None
    assert annualized_volatility_pct([100.0, 101.0, 102.0]) > 0


def test_compute_trend_indicators_from_demo_kline():
    source = DemoDataSource()
    kline = source.kline(Symbol.parse("600519"), days=120)
    ind = compute_trend_indicators(kline)
    assert ind.n_bars == 120
    assert ind.ma20 is not None
    assert ind.rsi14 is not None
    assert 0 <= ind.rsi14 <= 100
    assert ind.max_drawdown <= 0
    assert ind.as_of == kline.bars[-1].date.isoformat()
