from advisor.config import DataConfig, Settings
from advisor.datasources import build_default_router
from advisor.graph.nodes.research import _with_as_of
from advisor.tools.market_tools import build_market_tools


def test_kline_tool_truncates_at_as_of():
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    tools = build_market_tools(build_default_router(settings))
    kline_tool = next(t for t in tools if t.name == "get_daily_kline")
    wrapped = _with_as_of(kline_tool, "2025-06-30")

    import json

    payload = json.loads(wrapped.func("600519"))
    bars = payload["bars"]
    assert bars
    assert bars[-1]["date"] <= "2025-06-30"  # 源头截断：没有一根晚于截止日


def test_technical_indicator_tool_truncates_at_as_of():
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    tools = build_market_tools(build_default_router(settings))
    tech_tool = next(t for t in tools if t.name == "get_technical_indicators")
    wrapped = _with_as_of(tech_tool, "2025-06-30")

    import json

    payload = json.loads(wrapped.func("600519"))
    assert payload["as_of"] <= "2025-06-30"
