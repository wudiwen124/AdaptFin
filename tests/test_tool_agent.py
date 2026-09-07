from advisor.config import DataConfig, Settings
from advisor.datasources import build_default_router
from advisor.graph.nodes.agent import run_tool_agent
from advisor.tools.market_tools import build_market_tools
from tests.fake_gateway import FakeGateway


def test_tool_loop_executes_and_converges():
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    tools = build_market_tools(router)
    quote_tool = next(t for t in tools if t.name == "get_realtime_quote")
    gateway = FakeGateway(
        queue=[
            FakeGateway.tool_call("get_realtime_quote", {"symbol": "600519"}),
            FakeGateway._content("（演示）最新价 42.37 元，来源 demo。"),
        ]
    )
    run = run_tool_agent(
        gateway,
        system_prompt="你是行情专员",
        user_text="600519 多少钱",
        tools=[quote_tool],
        tier="deep",
    )
    assert run.tool_calls == ["get_realtime_quote"]
    assert len(run.observations) == 1
    assert run.observations[0].args["symbol"] == "600519"
    assert run.observations[0].output  # 原始工具输出进入证据记录
    assert run.observations[0].source == "demo"
    assert "来源" in run.text


def test_tool_error_becomes_observation_not_exception():
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    tools = build_market_tools(router)
    gateway = FakeGateway(
        queue=[
            FakeGateway.tool_call("get_realtime_quote", {"symbol": "999999"}),
            FakeGateway._content("数据不可用"),
        ]
    )
    run = run_tool_agent(
        gateway,
        system_prompt="你是行情专员",
        user_text="999999",
        tools=[tools[0]],
    )
    assert run.text == "数据不可用"
    assert run.tool_calls == ["get_realtime_quote"]
