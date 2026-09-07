"""投顾助手 HTTP 服务：SSE 聊天流 + 画像/审计查询。

启动示例：
    uvicorn advisor.service.app:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from advisor.config import Settings, load_settings
from advisor.datasources import DataSourceRouter, build_default_router
from advisor.graph.builder import build_app
from advisor.llm.client import ModelGateway, build_gateway
from advisor.store import ProfileStore


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    thread_id: str | None = Field(default=None, description="为空时按 user_id 隔离")
    message: str = Field(min_length=1)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_app(
    *,
    gateway: ModelGateway | None = None,
    router: DataSourceRouter | None = None,
    store: ProfileStore | None = None,
    graph: Any | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    gateway = gateway or build_gateway(settings)
    router = router or build_default_router(settings)
    store = store or ProfileStore(settings.store.db_path)
    graph = graph or build_app(gateway=gateway, router=router, store=store, settings=settings)

    fastapi_app = FastAPI(title="Multi-Agent Advisor API", version="0.1.0")

    @fastapi_app.get("/")
    def root() -> HTMLResponse:
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Multi-Agent Advisor API</title>
  <style>
    body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
           max-width: 720px; margin: 48px auto; padding: 0 20px; color: #1f2328; }
    h1 { font-size: 26px; }
    a { color: #0969da; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .card { border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 18px; margin: 10px 0; }
    code { background: #f6f8fa; padding: 2px 6px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>多 Agent 智能投顾助手 · API 服务</h1>
  <p>后端已启动。以下是可用的接口：</p>
  <div class="card"><a href="/docs"><strong>接口文档（推荐）</strong></a><br>FastAPI 交互式文档，可在线调试每个接口。</div>
  <div class="card"><code>POST /v1/chat</code> — SSE 聊天流<br>JSON：{"user_id": "demo", "thread_id": "main", "message": "600519"}</div>
  <div class="card"><code>GET /v1/profile/{user_id}</code> — 用户画像 / 持仓 / 风险历史</div>
  <div class="card"><code>GET /v1/audit</code> — 审计日志</div>
  <div class="card"><code>GET /health</code> — 健康检查</div>
</body>
</html>"""
        return HTMLResponse(content=html)

    @fastapi_app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @fastapi_app.post("/v1/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        request_id = uuid.uuid4().hex
        thread_id = request.thread_id or request.user_id

        async def event_stream():
            yield _sse("start", {"request_id": request_id, "thread_id": thread_id})
            try:
                result = await asyncio.to_thread(
                    graph.invoke,
                    {
                        "user_id": request.user_id,
                        "messages": [HumanMessage(content=request.message)],
                    },
                    {"configurable": {"thread_id": thread_id}},
                )
            except Exception as exc:
                yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
                return

            final = result.get("final_answer") or ""
            store.record_audit(
                request_id=request_id,
                user_id=request.user_id,
                intent=result.get("intent"),
                final_len=len(final),
                degraded=bool(result.get("sources")),
            )
            risk = result.get("risk_profile")
            yield _sse(
                "done",
                {
                    "request_id": request_id,
                    "intent": result.get("intent"),
                    "final_answer": final,
                    "sources": (result.get("sources") or [])[-8:],
                    "risk_level": risk.level.value if risk is not None else None,
                },
            )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @fastapi_app.get("/v1/profile/{user_id}")
    def profile(user_id: str) -> dict:
        profile = store.get_profile(user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {
            "profile": json.loads(profile.model_dump_json()),
            "holdings": [json.loads(h.model_dump_json()) for h in store.get_holdings(user_id)],
            "risk_history": store.risk_history(user_id),
        }

    @fastapi_app.get("/v1/audit")
    def audit(user_id: str | None = None, limit: int = 50) -> dict:
        return {"items": store.list_audit(user_id=user_id, limit=min(limit, 200))}

    return fastapi_app


app = create_app()
