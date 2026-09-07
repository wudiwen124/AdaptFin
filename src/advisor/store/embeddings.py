"""向量接入点：OpenAI 兼容 Embedder（智谱 / 硅基流动 SiliconFlow）+ cosine 纯函数。"""

from __future__ import annotations

import math
from typing import Any

import httpx

from advisor.config import Settings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class OpenAICompatEmbedder:
    """OpenAI 兼容 /embeddings 客户端（SiliconFlow BAAI/bge-m3、智谱 embedding 系列均适用）。"""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str = "BAAI/bge-m3",
        transport: Any = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
            transport=transport,
        )
        self.model = model

    def embed(self, text: str) -> list[float]:
        resp = self._client.post(
            "/embeddings",
            json={"model": self.model, "input": text[:2000]},
        )
        resp.raise_for_status()
        return [float(x) for x in resp.json()["data"][0]["embedding"]]


# 兼容旧引用
ZhipuEmbedder = OpenAICompatEmbedder


def build_embedder(settings: Settings | None = None) -> OpenAICompatEmbedder | None:
    """按配置构建 Embedder；off / 缺 key / 未实现类型时返回 None（走关键词召回）。"""
    settings = settings or Settings()
    if settings.memory.embedder not in {"zhipu", "siliconflow"}:
        return None
    import os

    if settings.memory.embedder == "siliconflow":
        api_key = os.environ.get(settings.memory.embed_api_key_env, "")
        base_url = (
            settings.memory.embed_base_url
            or os.environ.get("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
        )
    else:  # zhipu
        api_key = os.environ.get("LLM_API_KEY", "")
        base_url = settings.model.base_url or os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    if not api_key:
        return None
    return OpenAICompatEmbedder(api_key, base_url=base_url, model=settings.memory.embed_model)
