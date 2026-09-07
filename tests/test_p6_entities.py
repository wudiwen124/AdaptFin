from pathlib import Path

from langchain_core.messages import HumanMessage

from advisor.config import DataConfig, Settings, StoreConfig
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.store import ProfileStore
from advisor.llm.fake_gateway import FakeGateway


def _setup(tmp_path: Path):
    settings = Settings(
        data=DataConfig(sources_priority=["demo"]),
        store=StoreConfig(db_path=str(tmp_path / "p6.db"), checkpoint_db_path=str(tmp_path / "p6_ckpt.db")),
    )
    router = build_default_router(settings)
    store = ProfileStore(tmp_path / "p6.db")
    app = build_app(gateway=FakeGateway(), router=router, store=store, settings=settings)
    return app


def _ask(app, user: str, thread: str, text: str):
    return app.invoke(
        {"user_id": user, "messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread}},
    )


def test_pronoun_resolution_after_research(tmp_path):
    app = _setup(tmp_path)
    user, thread = "u_pr", "t_pr"
    first = _ask(app, user, thread, "贵州茅台现在怎么样")
    assert first["symbols"] == ["600519"]

    second = _ask(app, user, thread, "它现在多少钱")
    assert second["intent"] == "quote"
    assert second["symbols"] == ["600519"]
    assert second["query_gap"] is None
    assert len(second["tool_observations"]) > 0  # 真的去查了行情，而不是反问


def test_elliptical_followup_without_pronoun(tmp_path):
    app = _setup(tmp_path)
    user, thread = "u_el", "t_el"
    _ask(app, user, thread, "分析600519")
    second = _ask(app, user, thread, "走势呢")
    assert second["intent"] == "research"
    assert second["symbols"] == ["600519"]


def test_ambiguous_pronoun_uses_llm_resolver(tmp_path):
    app = _setup(tmp_path)
    user, thread = "u_am", "t_am"
    _ask(app, user, thread, "分析600519")
    _ask(app, user, thread, "分析510300")
    second = _ask(app, user, thread, "它最近怎么样")
    assert second["symbols"] == ["600519"]  # FakeGateway 的消解器取 600519


def test_context_entities_accumulate(tmp_path):
    app = _setup(tmp_path)
    user, thread = "u_ctx", "t_ctx"
    _ask(app, user, thread, "600519 现在多少钱")
    out = _ask(app, user, thread, "分析510300")
    codes = {e["code"] for e in out["context_entities"]}
    assert codes == {"600519", "510300"}
    assert out["turn_no"] == 2
