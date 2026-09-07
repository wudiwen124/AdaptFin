"""Research：多标的 fan-out（Send）+ 每个标的三维分析师并行。

路径：research/portfolio → send_research(Send 每标的) → research_node(3 分析师并行) → aggregator(fan-in) → Advisor。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from langchain_core.tools import BaseTool
from langchain_core.tools import Tool
from langgraph.types import Command, Send

from advisor.graph.nodes.agent import run_tool_agent
from advisor.graph.nodes.text import latest_user_text
from advisor.graph.state import AssistantState
from advisor.llm.client import ModelGateway
from advisor.schemas.research import ResearchReport


ANALYST_SYSTEMS = {
    "fundamentals": """你是基本面分析师。工具：公司概况/财务摘要/估值。
规则：只陈述工具返回的财务与估值事实（营收净利同比、ROE、PE/PB 及数据日期）；不预测股价；工具 error 时明说无数据。输出 150 字以内结论。""",
    "technical": """你是技术面分析师。工具：日K线/技术指标（MA、RSI、年化波动、最大回撤，均为本地确定性计算）。
规则：只描述指标数值与形态，不预测未来涨跌；工具 error 时明说无数据。输出 150 字以内结论。""",
    "news": """你是资讯/情绪分析师。工具：最近公开新闻公告。
规则：只归纳工具返回的标题与日期；把“对事件影响的解读”显式标注为推断，不写成事实；工具 error 时明说无数据。输出 150 字以内结论。""",
}

ANALYST_TOOLS = {
    "fundamentals": {"get_company_profile", "get_financial_summary", "get_valuation"},
    "technical": {"get_daily_kline", "get_technical_indicators"},
    "news": {"get_recent_news", "get_company_profile"},
}


def send_research(state: AssistantState) -> Command:
    symbols = state.get("symbols") or []
    user_text = latest_user_text(state.get("messages") or [])
    as_of = state.get("as_of_date")
    return Command(
        goto=[
            Send(
                "research_node",
                {"symbol": sym, "user_text": user_text, "as_of": as_of},
            )
            for sym in symbols
        ]
    )


def research_one_node(
    state: dict,
    *,
    gateway: ModelGateway,
    tools: list[BaseTool],
) -> dict:
    symbol = state.get("symbol", "")
    user_text = state.get("user_text", "")
    as_of = state.get("as_of")
    if as_of:
        user_text = f"{user_text}（研究截止日：{as_of}，请只使用该日期前可见的数据）"
    by_name = {t.name: t for t in tools}

    def analyst(kind: str):
        try:
            tool_list = [by_name[name] for name in ANALYST_TOOLS[kind] if name in by_name]
            if kind == "technical" and as_of:
                # P14-A：研究截止日在源头截断 K 线，晚数据不进证据区
                tool_list = [_with_as_of(t, as_of) for t in tool_list]
            run = run_tool_agent(
                gateway,
                system_prompt=ANALYST_SYSTEMS[kind],
                user_text=f"标的 {symbol}。用户问题：{user_text}",
                tools=tool_list,
                tier="deep",
                max_steps=3,
            )
            return kind, run.text, run.sources, run.observations
        except Exception as exc:  # 单个分析师失败只降级该维度，不让整轮研究崩掉
            return kind, f"该维度分析暂不可用：{exc}", [f"{kind}:error"], []

    parts: list[str] = []
    sources: list[str] = []
    observations: list = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for kind, text, srcs, obs in pool.map(lambda k: analyst(k), ANALYST_SYSTEMS.keys()):
            parts.append(f"【{kind}】\n{text}")
            sources.extend(srcs)
            observations.extend(obs)

    report = ResearchReport(
        symbol=symbol,
        summary="\n\n".join(parts),
        claims=[],  # P3：由 Auditor 从工具观察生成确定性 Claim
        as_of=date.today().isoformat(),
    )
    return {"research_results": [report], "sources": sources, "tool_observations": observations}


def aggregator_node(state: AssistantState) -> dict:
    """fan-in 汇聚点：多个 research_node 分支的结果已合并进 research_results，无需额外逻辑。"""
    return {}


def _with_as_of(tool: BaseTool, as_of: str) -> Tool:
    """包装日 K/指标工具：强制 end_date=as_of。"""

    def func(symbol: str, start_date: str | None = None, end_date: str | None = None, **kwargs):
        extra = {k: v for k, v in kwargs.items() if k not in ("start_date", "end_date")}
        if tool.name == "get_daily_kline":
            return tool.func(symbol, start_date=start_date, end_date=as_of, **extra)
        return tool.func(symbol, end_date=as_of, **extra)

    return Tool(name=tool.name, description=tool.description or "", args_schema=tool.args_schema, func=func)
