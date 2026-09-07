"""Supervisor：意图路由 + 名称解析 + 加载画像 + 组装用户记忆 + 每轮状态清理。"""

from __future__ import annotations

import re

from advisor.graph.nodes.text import latest_user_text
from advisor.graph.state import RESET, AssistantState
from advisor.llm.client import ModelGateway
from advisor.orchestration.entities import entity_payload, resolve_target
from advisor.orchestration.resolver import resolve_names
from advisor.orchestration.router import RouteResult, route_request
from advisor.store import ProfileStore
from advisor.store.embeddings import ZhipuEmbedder


def _build_user_memory(
    profile,
    holdings,
    store,
    user_id,
    query_text: str,
    embedder: ZhipuEmbedder | None = None,
) -> str:
    """把 SQLite 画像变成 Advisor 可读的记忆块（P5-A：补上“读”侧）。"""
    lines: list[str] = []
    if profile is None:
        return ""
    if profile.facts:
        recalled = (
            store.recall_memory(user_id, query_text, limit=5, embedder=embedder)
            if store and query_text
            else []
        )
        facts_source = recalled or profile.facts[:20]
        tag = "相关记忆（按相关度）" if recalled else "用户事实"
        lines.append(f"{tag}：" + "；".join(facts_source))
    if profile.prefs:
        prefs = "；".join(f"{k}: {v}" for k, v in profile.prefs.items())
        lines.append(f"用户偏好：{prefs}")
    if holdings:
        parts = []
        for h in holdings[:20]:
            qty = f"{h.qty:g}" if h.qty else "数量未知"
            cost = f"，成本 {h.cost}" if h.cost else ""
            parts.append(f"{h.symbol}({qty}{cost})")
        lines.append("用户持仓：" + "、".join(parts))
    return "\n".join(lines)


def supervisor_node(
    state: AssistantState,
    *,
    gateway: ModelGateway,
    store: ProfileStore,
    embedder: ZhipuEmbedder | None = None,
) -> dict:
    text = latest_user_text(state.get("messages") or [])
    as_of_date = _extract_as_of(text)
    user_id = state.get("user_id", "")
    profile = store.get_profile(user_id) if user_id else None

    # 问卷进行中（含“重新测评”）：答题文本先于路由锁定 risk，且零 LLM 调用
    questionnaire_active = False
    if (state.get("q_index") or 0) > 0 and not state.get("risk_done", False):
        route = RouteResult(intent="risk", confidence=1.0)
        questionnaire_active = True
    elif "吴帝文" in text:
        # 固定人物事实：锁定 chat，避免被路由成 research 后走金融模板
        route = RouteResult(intent="chat", confidence=1.0)
    else:
        try:
            route = route_request(text, gateway=gateway)
        except Exception:
            route = RouteResult(intent="chat", confidence=0.5, source="fallback")

    holdings = []
    entity_codes: set[str] = set()
    if route.intent == "portfolio":
        holdings = store.get_holdings(user_id) if user_id else []
        if holdings:
            route.symbols = [h.symbol for h in holdings if h.symbol[:6].isdigit()] or route.symbols
            entity_codes.update(route.symbols)

    # P5-B：名称 → 代码（“贵州茅台” 也能触发研究/行情）
    if route.intent in {"quote", "research"} and not route.symbols:
        route.symbols = resolve_names(text)
    entity_codes.update(route.symbols)

    # P6-A：指代消解——“它/这只/那个” → 最近提到的标的
    if route.intent in {"quote", "research", "portfolio"} and not route.symbols:
        resolved = resolve_target(gateway, text, state.get("context_entities") or [])
        if resolved:
            route.symbols = [resolved]
            entity_codes.add(resolved)

    query_gap = None
    if route.intent in {"quote", "research"} and not route.symbols:
        query_gap = "缺少具体标的：请询问用户要查询哪只股票/ETF（6 位代码或名称），不要编造分析。"
    elif route.intent == "portfolio" and not holdings and not route.symbols:
        query_gap = "用户还没有持仓记录：请引导用户提供持仓（如“买入 100 股 510300”）。"

    injected_risk = profile.risk if profile else None
    if questionnaire_active:
        injected_risk = None  # 重做期间不把旧画像塞回 state，避免顶掉问卷

    turn_no = int(state.get("turn_no", 0)) + 1

    return {
        "intent": route.intent,
        "symbols": route.symbols,
        "holdings": holdings,
        "risk_profile": injected_risk,
        "user_memory": _build_user_memory(profile, holdings, store, user_id, text, embedder),
        "query_gap": query_gap,
        "as_of_date": as_of_date,
        "turn_no": turn_no,
        "context_entities": [entity_payload(code, turn_no) for code in sorted(entity_codes)],
        "agent_context": None,
        "final_answer": None,
        # turn 级清理：清空上一轮研究/证据，防止污染新问题
        "research_results": [RESET],
        "tool_observations": [RESET],
        "sources": [RESET],
    }


def _extract_as_of(text: str) -> str | None:
    """识别“2025-06-30 / 2025年6月30日”并归一化为 YYYY-MM-DD。"""
    m = re.search(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?", text)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), m.group(3)
    return f"{year}-{month:02d}" + (f"-{int(day):02d}" if day else "")
