from pathlib import Path

from fastapi.testclient import TestClient

from advisor.config import DataConfig, Settings
from advisor.datasources import build_default_router
from advisor.service.app import create_app
from advisor.store import ProfileStore
from tests.fake_gateway import FakeGateway


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    store = ProfileStore(tmp_path / "service.db")
    app = create_app(gateway=FakeGateway(), router=router, store=store, settings=settings)
    return TestClient(app), store


def test_health(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}
    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]
    assert "Multi-Agent Advisor API" in root.text


def test_chat_sse_done_event(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post("/v1/chat", json={"user_id": "u_svc", "thread_id": "t1", "message": "600519现在多少钱"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: start" in body
    assert "event: done" in body
    assert "不构成投资建议" in body


def test_chat_memory_then_profile_endpoint(tmp_path):
    client, store = _client(tmp_path)
    client.post(
        "/v1/chat",
        json={"user_id": "u_svc2", "thread_id": "t2", "message": "我买了100股510300"},
    )
    profile_resp = client.get("/v1/profile/u_svc2")
    assert profile_resp.status_code == 200
    data = profile_resp.json()
    assert data["holdings"][0]["symbol"] == "510300"
    assert data["holdings"][0]["qty"] == 100


def test_profile_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/v1/profile/nobody").status_code == 404
