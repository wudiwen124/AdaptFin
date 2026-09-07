from pathlib import Path

import httpx

from langchain_core.messages import HumanMessage

from advisor.config import DataConfig, Settings, StoreConfig
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.store import ProfileStore
from advisor.store.embeddings import OpenAICompatEmbedder
from advisor.llm.fake_gateway import FakeGateway


class FakeEmbedder:
    """确定性测试 Embedder：按输入返回手工向量。"""

    VECTORS = {
        "红利低波": [1.0, 0.0, 0.0],
        "低波动高分红": [0.98, 0.05, 0.0],
        "无关问题": [0.0, 0.0, 1.0],
    }

    def embed(self, text: str) -> list[float]:
        for key in self.VECTORS:
            if key in text:
                return self.VECTORS[key]
        return self.VECTORS["无关问题"]


def _settings(tmp_path: Path):
    return Settings(
        data=DataConfig(sources_priority=["demo"]),
        store=StoreConfig(db_path=str(tmp_path / "p.db"), checkpoint_db_path=str(tmp_path / "ck.db")),
    )


def test_store_vector_recall(tmp_path):
    store = ProfileStore(tmp_path / "p2.db")
    store.add_fact("u1", "红利低波")
    store.save_fact_embedding("u1", "红利低波", FakeEmbedder().embed("红利低波"))

    hit = store.recall_memory("u1", "低波动高分红", embedder=FakeEmbedder(), min_similarity=0.9)
    assert hit and "红利低波" in hit[0]

    miss = store.recall_memory("u1", "无关问题", embedder=FakeEmbedder(), min_similarity=0.9)
    assert miss == []


def test_memory_writer_saves_embedding_when_enabled(tmp_path):
    settings = _settings(tmp_path)
    store = ProfileStore(settings.store.db_path)
    app = build_app(
        gateway=FakeGateway(),
        router=build_default_router(settings),
        store=store,
        settings=settings,
        embedder=FakeEmbedder(),
    )
    app.invoke(
        {"user_id": "u_emb", "messages": [HumanMessage(content="我买了100股510300，偏好红利低波")]},
        config={"configurable": {"thread_id": "t_emb"}},
    )
    with store._connect() as conn:  # 内部连接仅测试用
        n = conn.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0]
    assert n >= 1


def test_siliconflow_embedder_api_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b"BAAI/bge-m3" in body
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
        )

    embedder = OpenAICompatEmbedder(
        "test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="BAAI/bge-m3",
        transport=httpx.MockTransport(handler),
    )
    assert embedder.embed("红利低波") == [0.1, 0.2, 0.3]


def test_backfill_pending_list(tmp_path):
    store = ProfileStore(tmp_path / "bf.db")
    store.add_fact("u_bf", "偏好红利低波")
    pending = store.list_unembedded_facts()
    assert pending == [("u_bf", "偏好红利低波")]
    store.save_fact_embedding("u_bf", "偏好红利低波", [1.0, 0.0])
    assert store.list_unembedded_facts() == []
