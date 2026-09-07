"""Memory Writer：把本轮结论写回长期画像/会话。

P2 范围：风险画像落库 + 把 assistant 最终回答追加进 messages（供 checkpoint 续聊）。
P4 扩展：偏好/持仓抽取（LLM 结构化 + 字段级审计写入）。
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from advisor.graph.nodes.extract import extract_memory_updates, llm_extract_facts
from advisor.graph.nodes.text import latest_user_text
from advisor.graph.state import AssistantState
from advisor.llm.client import ModelGateway
from advisor.store import ProfileStore
from advisor.store.embeddings import ZhipuEmbedder


def memory_writer_node(
    state: AssistantState,
    *,
    store: ProfileStore,
    gateway: ModelGateway,
    embedder: ZhipuEmbedder | None = None,
) -> dict:
    updates: dict = {}
    user_id = state.get("user_id", "")
    user_text = latest_user_text(state.get("messages") or [])
    if user_id and user_text:
        holdings, removed, facts = extract_memory_updates(user_text)
        for holding in holdings:
            store.add_holding(user_id, holding)
        for symbol in removed:
            store.remove_holding(user_id, symbol)
        for fact in facts:
            store.add_fact(user_id, fact)
            if embedder is not None:
                _embed_and_save(store, embedder, user_id, fact)
        if not facts:
            for fact in llm_extract_facts(gateway, user_text):
                store.add_fact(user_id, fact)
                if embedder is not None:
                    _embed_and_save(store, embedder, user_id, fact)
    risk = state.get("risk_profile")
    if user_id and risk is not None and state.get("risk_dirty"):
        store.set_risk(user_id, risk)
    updates["risk_dirty"] = False  # 无论是否写库，本轮“新结果”标记消费后即复位
    final = state.get("final_answer")
    if final:
        last = (state.get("messages") or [None])[-1]
        role = getattr(last, "type", None) or (last.get("type") if isinstance(last, dict) else None)
        if role != "ai" or getattr(last, "content", None) != final:
            updates["messages"] = [AIMessage(content=final)]
    return updates


def _embed_and_save(store: ProfileStore, embedder: ZhipuEmbedder, user_id: str, fact: str) -> None:
    try:
        store.save_fact_embedding(user_id, fact, embedder.embed(fact))
    except Exception:
        pass  # embedding 失败不影响记忆落库，下一轮可重试/回退关键词
