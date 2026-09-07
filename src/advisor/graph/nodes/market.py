"""Market Agent：只取数、不评价。产出 agent_context 供 Advisor 合成。"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from advisor.graph.nodes.agent import run_tool_agent
from advisor.graph.nodes.text import latest_user_text
from advisor.graph.state import AssistantState
from advisor.llm.client import ModelGateway

MARKET_SYSTEM = """你是行情查询专员。
规则：
1. 只调用行情类工具回答问题（实时行情/指数快照），不要调用财务、新闻工具。
2. 只陈述工具返回的事实：价格、涨跌幅、成交额、行情时间；不解释原因、不给预测、不给建议。
3. 工具返回 error 时如实说“当前数据源不可用”，不要编造数字。
4. 用中文回答，控制在 120 字以内，结尾列出数据来源与时间。
5. 禁止在回答中出现 get_ 开头的工具名，来源写“行情数据源”。"""


def market_node(state: AssistantState, *, gateway: ModelGateway, tools: list[BaseTool]) -> dict:
    original = latest_user_text(state.get("messages") or [])
    user_text = f"查询标的 {'、'.join(state.get('symbols') or [])}；用户原话：{original}"
    try:
        run = run_tool_agent(
            gateway,
            system_prompt=MARKET_SYSTEM,
            user_text=user_text,
            tools=[t for t in tools if t.name in {"get_realtime_quote", "get_index_snapshot"}],
            tier="deep",
        )
        return {
            "agent_context": run.text,
            "sources": run.sources,
            "tool_observations": run.observations,
        }
    except Exception as exc:
        return {"agent_context": f"行情查询暂不可用：{exc}", "sources": ["market:error"]}
