from advisor.store import ProfileStore
from advisor.store.embeddings import cosine_similarity
from advisor.store.recall import score_facts


def _store(tmp_path):
    return ProfileStore(tmp_path / "recall.db")


def test_paraphrase_recall_via_synonym_group(tmp_path):
    store = _store(tmp_path)
    store.add_fact("u1", "用户偏好红利低波")
    store.add_fact("u1", "用户不喜欢频繁交易")
    store.add_fact("u1", "用户偏好消费板块")

    hit = store.recall_memory("u1", "我喜欢低波动高分红的方向", limit=5)
    assert hit and "红利低波" in hit[0]

    hit2 = store.recall_memory("u1", "我是不是说过不想做短线", limit=5)
    assert hit2 and "频繁交易" in hit2[0]


def test_unrelated_query_returns_nothing(tmp_path):
    store = _store(tmp_path)
    store.add_fact("u1", "用户偏好红利低波")
    assert store.recall_memory("u1", "帮我查一下600519行情") == []


def test_score_facts_direct_substring_ranked_first():
    scored = score_facts(["用户偏好红利低波", "红利低波 是我的方向"], "红利低波 是我的方向")
    assert scored[0][0] == "红利低波 是我的方向"


def test_cosine_similarity_basic():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_recall_used_by_supervisor_user_memory(tmp_path):
    from langchain_core.messages import HumanMessage

    from advisor.config import DataConfig, Settings, StoreConfig
    from advisor.datasources import build_default_router
    from advisor.graph.builder import build_app
    from advisor.llm.fake_gateway import FakeGateway

    settings = Settings(
        data=DataConfig(sources_priority=["demo"]),
        store=StoreConfig(db_path=str(tmp_path / "s.db"), checkpoint_db_path=str(tmp_path / "ck.db")),
    )
    store = ProfileStore(settings.store.db_path)
    store.add_fact("u_mem", "用户偏好红利低波")
    app = build_app(
        gateway=FakeGateway(),
        router=build_default_router(settings),
        store=store,
        settings=settings,
    )
    out = app.invoke(
        {
            "user_id": "u_mem",
            "messages": [HumanMessage(content="低波动高分红的方向我还提过别的吗")],
        },
        config={"configurable": {"thread_id": "t_mem"}},
    )
    assert out["user_memory"] is not None
    assert "红利低波" in out["user_memory"]
