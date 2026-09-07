from pathlib import Path

from langchain_core.messages import HumanMessage

from advisor.config import DataConfig, Settings, StoreConfig
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.orchestration.resolver import resolve_names
from advisor.store import ProfileStore
from tests.fake_gateway import FakeGateway


def _app(tmp_path: Path, settings: Settings | None = None):
    settings = settings or Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    store = ProfileStore(settings.store.db_path)
    app = build_app(gateway=FakeGateway(), router=router, store=store, settings=settings)
    return app, store


def _ask(app, user_id: str, thread: str, text: str):
    return app.invoke(
        {"user_id": user_id, "messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread}},
    )


def test_resolver_names():
    assert resolve_names("帮我看看贵州茅台") == ["600519"]
    assert resolve_names("宁德时代 300750") == ["300750"]
    assert resolve_names("随便聊聊") == []


def test_name_query_resolves_to_research(tmp_path):
    app, _ = _app(tmp_path)
    out = _ask(app, "u_name", "t_name", "贵州茅台现在怎么样")
    assert out["intent"] == "research"
    assert out["symbols"] == ["600519"]
    assert len(out["research_results"]) == 1


def test_unknown_target_asks_clarification(tmp_path):
    app, _ = _app(tmp_path)
    out = _ask(app, "u_unknown", "t_unknown", "帮我分析那个高股息标的")
    assert out["intent"] == "research"
    assert out["symbols"] == []
    assert out["query_gap"] is not None
    assert out["research_results"] == []


def test_user_memory_is_read_back(tmp_path):
    app, store = _app(tmp_path)
    user, thread = "u_read", "t_read"
    _ask(app, user, thread, "我买了100股510300，不喜欢频繁交易")

    out = _ask(app, user, thread, "分析我的持仓")  # 同一线程：验证跨轮清理
    assert len(out["research_results"]) == 1  # 旧轮结果已被 RESET，未累加
    assert out["user_memory"] is not None
    assert "510300" in out["user_memory"]
    assert "不喜欢频繁交易" in out["user_memory"]
    assert store.get_profile(user) is not None


def test_checkpoint_survives_app_restart(tmp_path):
    settings = Settings(
        data=DataConfig(sources_priority=["demo"]),
        store=StoreConfig(db_path=str(tmp_path / "p.db"), checkpoint_db_path=str(tmp_path / "ckpt.db")),
    )
    app1, _ = _app(tmp_path, settings)
    first = _ask(app1, "u_persist", "t_persist", "我想做风险测评")
    assert first["q_index"] == 1

    # 模拟服务重启：同一 db/checkpoint 路径重新编译一个新 app
    app2, _ = _app(tmp_path, settings)
    second = _ask(app2, "u_persist", "t_persist", "1")
    assert second["q_index"] == 2  # 从 checkpoint 恢复，而不是重新开始
    assert "2/10" in (second["final_answer"] or "")
