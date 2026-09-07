import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage

from advisor.config import DataConfig, Settings
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.graph.state import initial_state
from advisor.store import ProfileStore
from tests.fake_gateway import FakeGateway


def _app(tmp_path: Path):
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    store = ProfileStore(tmp_path / "graph.db")
    return build_app(gateway=FakeGateway(), router=router, store=store, settings=settings), store


def _app_with_gateway(tmp_path: Path):
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    store = ProfileStore(tmp_path / "graph2.db")
    gateway = FakeGateway()
    app = build_app(gateway=gateway, router=router, store=store, settings=settings)
    return app, store, gateway


def _invoke(app, user_id: str, thread: str, text: str):
    return app.invoke(
        initial_state(user_id, [HumanMessage(content=text)]),
        config={"configurable": {"thread_id": thread}},
    )


def _continue(app, user_id: str, thread: str, text: str):
    """多轮续聊：只追加 user_id 与消息，保留 checkpoint 中的问卷进度。"""
    return app.invoke(
        {"user_id": user_id, "messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread}},
    )


def test_quote_flow(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_q", "t_q", "贵州茅台600519现在多少钱")
    assert out["intent"] == "quote"
    assert "不构成投资建议" in (out["final_answer"] or "")


def test_research_fanout_single(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_r", "t_r", "分析600519的基本面和技术面")
    assert out["intent"] == "research"
    assert len(out["research_results"]) == 1
    assert out["research_results"][0].symbol == "600519"
    assert "不构成投资建议" in (out["final_answer"] or "")


def test_risk_flow_persists_profile(tmp_path):
    app, store = _app(tmp_path)
    first = _invoke(app, "u_k", "t_k", "我想做风险测评")
    assert "1/10" in (first["final_answer"] or "")
    assert first["q_index"] == 1

    for _ in range(10):
        out = _continue(app, "u_k", "t_k", "1")  # 每题选第 1 项 → 全 1 分
    assert out["risk_done"] is True
    assert "C1" in (out["final_answer"] or "")
    profile = store.get_profile("u_k")
    assert profile is not None and profile.risk.level.value == "C1"


def test_risk_flow_does_not_call_llm_for_answers(tmp_path):
    """答题轮必须零 LLM 调用（规则编号命中 + Supervisor 先行覆盖），防模板回显崩掉整轮。"""
    app, store, gateway = _app_with_gateway(tmp_path)
    first = _invoke(app, "u_k2", "t_k2", "我想做风险测评")
    assert first["q_index"] == 1
    for _ in range(10):
        out = _continue(app, "u_k2", "t_k2", "1")
    assert out["risk_done"] is True
    assert gateway.calls == []  # 全程未调用模型
    assert store.get_profile("u_k2").risk.level.value == "C1"


def _complete_c1(app, store, user: str, thread: str):
    _invoke(app, user, thread, "我想做风险测评")
    for _ in range(10):
        _continue(app, user, thread, "1")
    assert store.get_profile(user).risk.level.value == "C1"


def test_risk_query_is_readonly(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_qr", "t_qr"
    _complete_c1(app, store, user, thread)
    assert len(store.risk_history(user)) == 1

    out = _continue(app, user, thread, "我的风险等级是多少")
    assert "C1" in (out["final_answer"] or "")
    assert store.get_profile(user).risk.level.value == "C1"
    assert len(store.risk_history(user)) == 1  # 查询不产生新记录


def test_risk_redo_updates_level_and_keeps_history(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_redo", "t_redo"
    _complete_c1(app, store, user, thread)

    start = _continue(app, user, thread, "我想重新测评")
    assert start["q_index"] == 1
    assert start["risk_profile"] is None
    assert "重新测评中" in (start["final_answer"] or "")

    for _ in range(10):
        out = _continue(app, user, thread, "4")  # 每题选第 4 项（6 分）→ C5
    assert out["risk_done"] is True
    assert "C5" in (out["final_answer"] or "")
    assert "已由 C1 更新为 C5" in (out["final_answer"] or "")
    assert store.get_profile(user).risk.level.value == "C5"
    assert [h["level"] for h in store.risk_history(user)] == ["C1", "C5"]


def test_risk_redo_cancel_keeps_old_level(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_cancel", "t_cancel"
    _complete_c1(app, store, user, thread)

    _continue(app, user, thread, "我想重新测评")
    out = _continue(app, user, thread, "取消测评")
    assert out["q_index"] == 0
    assert "保持不变" in (out["final_answer"] or "")
    assert store.get_profile(user).risk.level.value == "C1"
    assert len(store.risk_history(user)) == 1

    # 取消后恢复正常路由（不会被问卷流程卡住）
    quote = _continue(app, user, thread, "600519现在多少钱")
    assert quote["intent"] == "quote"


def test_portfolio_without_holdings_goes_to_advisor(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_p", "t_p", "分析一下我的持仓")
    assert out["intent"] == "portfolio"
    assert (out["final_answer"] or "").strip()


def test_chat_greeting_is_conversational(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_greet", "t_greet", "你好，介绍一下你能做什么")
    assert out["intent"] == "chat"
    final = out["final_answer"] or ""
    assert "结论摘要" not in final
    assert "不构成投资建议" not in final
    assert "AdaptFin" in final


def test_who_is_wudiwen_deterministic_answer(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_dev", "t_dev", "吴帝文是谁？")
    assert out["intent"] == "chat"
    assert "吴帝文是 AdaptFin 的开发者" in (out["final_answer"] or "")


def test_wudiwen_not_routed_to_research(tmp_path):
    app, _ = _app(tmp_path)
    out = _invoke(app, "u_dev2", "t_dev2", "分析一下吴帝文是谁")
    assert out["intent"] == "chat"  # 即使含“分析”也不走研究
    final = out["final_answer"] or ""
    assert "吴帝文是 AdaptFin 的开发者" in final
    assert "结论摘要" not in final and "不构成投资建议" not in final


def test_memory_extracts_holdings_and_prefs_then_portfolio_uses_them(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_mem", "t_mem"

    first = _invoke(app, user, thread, "我买了100股510300，不喜欢频繁交易")
    assert first["intent"] == "portfolio"
    profile = store.get_profile(user)
    assert [h.symbol for h in profile.holdings] == ["510300"]
    assert profile.holdings[0].qty == 100
    assert any("不喜欢频繁交易" in f for f in profile.facts)

    second = _continue(app, user, thread, "分析我的持仓")
    assert second["intent"] == "portfolio"
    assert len(second["research_results"]) == 1
    assert second["research_results"][0].symbol == "510300"


def test_memory_removes_sold_holding(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_sell", "t_sell"
    _invoke(app, user, thread, "我持有600519")
    assert [h.symbol for h in store.get_holdings(user)] == ["600519"]
    _continue(app, user, thread, "卖出600519")
    assert store.get_holdings(user) == []
