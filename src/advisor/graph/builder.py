"""LangGraph 图编译：Supervisor → 分支（Market/Research fan-out/Risk/Chat）→ Advisor → Auditor → Memory。"""

from __future__ import annotations

import sqlite3
from functools import partial
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from advisor.config import Settings, load_settings
from advisor.datasources import DataSourceRouter, build_default_router
from advisor.graph.nodes import (
    after_audit,
    after_risk,
    advisor_node,
    aggregator_node,
    auditor_node,
    market_node,
    memory_writer_node,
    research_one_node,
    risk_node,
    send_research,
    supervisor_node,
)
from advisor.graph.state import AssistantState
from advisor.llm.client import ModelGateway, build_gateway
from advisor.store import ProfileStore
from advisor.store.embeddings import build_embedder
from advisor.tools.market_tools import build_market_tools


def _make_serde() -> JsonPlusSerializer:
    """带显式 msgpack 白名单的序列化器，避免自定义类型告警/未来拦截。"""
    return JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("advisor.schemas.risk", "RiskProfile"),
            ("advisor.schemas.risk", "RiskLevel"),
            ("advisor.schemas.risk", "Constraints"),
            ("advisor.schemas.risk", "QuestionOption"),
            ("advisor.schemas.user", "UserProfile"),
            ("advisor.schemas.user", "Holding"),
            ("advisor.schemas.research", "ResearchReport"),
            ("advisor.schemas.research", "Claim"),
            ("advisor.schemas.research", "EvidenceRecord"),
        ]
    )


def _default_checkpointer(db_path: str | Path | None = None):
    """默认持久 checkpoint：SqliteSaver（可跨进程重启），缺依赖时退回 MemorySaver。"""
    serde = _make_serde()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415
    except ImportError:
        return MemorySaver(serde=serde)
    path = Path(db_path) if db_path else Path("data/checkpoints.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    # 官方要求：内部用锁保护，因此允许跨线程使用
    conn = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(conn=conn, serde=serde)


def _route_from_supervisor(state: AssistantState) -> str:
    intent = state.get("intent") or "chat"
    if intent in {"research", "portfolio"}:
        return "send_research" if state.get("symbols") else "advisor_node"
    return {
        "quote": "market_node",
        "risk": "risk_node",
        "chat": "advisor_node",
    }.get(intent, "advisor_node")


def build_app(
    *,
    gateway: ModelGateway | None = None,
    router: DataSourceRouter | None = None,
    store: ProfileStore | None = None,
    checkpointer=None,
    settings: Settings | None = None,
    embedder=None,
) -> object:
    """编译主图。checkpointer 默认 MemorySaver；生产可换 SqliteSaver。"""
    settings = settings or load_settings()
    gateway = gateway or build_gateway(settings)
    router = router or build_default_router(settings)
    store = store or ProfileStore(settings.store.db_path)
    embedder = embedder if embedder is not None else build_embedder(settings)
    tools = build_market_tools(router)

    g = StateGraph(AssistantState)
    g.add_node("supervisor", partial(supervisor_node, gateway=gateway, store=store, embedder=embedder))
    g.add_node("market_node", partial(market_node, gateway=gateway, tools=tools))
    g.add_node("send_research", send_research)
    g.add_node("research_node", partial(research_one_node, gateway=gateway, tools=tools))
    g.add_node("aggregator_node", aggregator_node)
    g.add_node("risk_node", partial(risk_node, gateway=gateway, store=store))
    g.add_node("advisor_node", partial(advisor_node, gateway=gateway))
    g.add_node("auditor_node", partial(auditor_node, max_rounds=settings.risk.max_audit_rounds))
    g.add_node(
        "memory_writer_node",
        partial(memory_writer_node, store=store, gateway=gateway, embedder=embedder),
    )

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route_from_supervisor)
    g.add_edge("market_node", "advisor_node")
    g.add_edge("research_node", "aggregator_node")
    g.add_edge("aggregator_node", "advisor_node")
    g.add_conditional_edges("risk_node", after_risk, {"memory_writer": "memory_writer_node", END: END})
    g.add_edge("advisor_node", "auditor_node")
    g.add_conditional_edges(
        "auditor_node",
        after_audit,
        {"advisor": "advisor_node", "memory_writer": "memory_writer_node"},
    )
    g.add_edge("memory_writer_node", END)

    return g.compile(checkpointer=checkpointer or _default_checkpointer(settings.store.checkpoint_db_path))
