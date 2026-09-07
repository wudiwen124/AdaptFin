"""LangGraph State 契约（P0 定稿，P2/P3 由各节点读写）。

关键点：messages 走 add_messages 归约（checkpoint 持久化）；
research_results / sources 用 operator.add 支持 Send 并行 fan-in；
问卷进度（q_index/q_scores）随 checkpoint 跨轮保留。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages

from advisor.schemas.risk import RiskProfile
from advisor.schemas.user import Holding

Intent = Literal["quote", "research", "portfolio", "risk", "chat"]


RESET = "_TURN_RESET_"  # turn 级清理哨兵（必须可被 checkpoint 序列化）


def _turn_list(current, updates):
    """research_results/sources/tool_observations 的归约器：
    收到 RESET 标记则整表替换（新轮次），否则追加（并行 fan-in）。"""
    if any(u == RESET for u in updates):
        return [u for u in updates if u != RESET]
    return list(current or []) + list(updates)


def _merge_entities(current, updates):
    """实体注册表按 code 合并（每轮 Supervisor 写入全量，跨轮保留计数/活跃度）。"""
    merged = {e["code"]: dict(e) for e in current or [] if "code" in e}
    for update in updates or []:
        item = dict(update)
        code = item.get("code")
        if code is None:
            continue
        prev = merged.get(code)
        if prev:
            item["count"] = int(prev.get("count", 0)) + int(item.get("count", 1))
            item["last_seen"] = max(prev.get("last_seen", 0), item.get("last_seen", 0))
        merged[code] = item
    return list(merged.values())


class AssistantState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    user_id: str
    intent: Intent | None
    symbols: list[str]
    holdings: list[Holding] | None
    risk_profile: RiskProfile | None
    research_results: Annotated[list[Any], _turn_list]
    tool_observations: Annotated[list[Any], _turn_list]
    sources: Annotated[list[str], _turn_list]
    context_entities: Annotated[list[dict], _merge_entities]
    turn_no: int
    agent_context: str | None
    user_memory: str | None     # 由 Supervisor 组装：facts/prefs/holdings 摘要
    query_gap: str | None       # 证据缺口提示（如缺少标的代码）→ Advisor 改为反问
    as_of_date: str | None      # 用户指定的研究截止日（YYYY-MM-DD），PIT 守卫用
    tool_results: dict[str, Any]
    audit_round: int
    audit_issue: str | None
    q_index: int
    q_scores: list[int]
    risk_done: bool
    risk_dirty: bool  # 本轮回答是否产生了新的测评结果（避免“查询画像”重复写库）
    final_answer: str | None


def initial_state(user_id: str, messages: list[Any] | None = None) -> dict[str, Any]:
    """构造一次图调用的初始 state。messages 建议传 langchain_core 的 HumanMessage。"""
    return {
        "messages": messages or [],
        "user_id": user_id,
        "intent": None,
        "symbols": [],
        "holdings": None,
        "risk_profile": None,
        "research_results": [],
        "tool_observations": [],
        "sources": [],
        "context_entities": [],
        "turn_no": 0,
        "agent_context": None,
        "user_memory": None,
        "query_gap": None,
        "as_of_date": None,
        "tool_results": {},
        "audit_round": 0,
        "audit_issue": None,
        "q_index": 0,
        "q_scores": [],
        "risk_done": False,
        "risk_dirty": False,
        "final_answer": None,
    }
