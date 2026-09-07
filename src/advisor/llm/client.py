"""模型网关：OpenAI 兼容接口 + 分档（router/deep）。

默认接入智谱 BigModel（与用户提供的 GLM key 匹配）；任何 OpenAI 兼容端点均可替换。
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from advisor.config import ModelConfig, Settings, load_settings

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class ModelGateway:
    """同步 OpenAI 兼容 chat completions 客户端，支持 tools/tool_choice。"""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        router_model: str = "glm-4.7-flash",
        deep_model: str = "glm-4.7-flash",
        read_timeout_seconds: float = 120.0,
        connect_timeout_seconds: float = 15.0,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
        router_fallbacks: list[str] | None = None,
        deep_fallbacks: list[str] | None = None,
        transport: Any = None,
    ) -> None:
        self.router_model = router_model
        self.deep_model = deep_model
        self._models = {
            "router": _dedupe([router_model, *(router_fallbacks or ["glm-4-flash"])]),
            "deep": _dedupe([deep_model, *(deep_fallbacks or ["glm-4-flash"])]),
        }
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=read_timeout_seconds,
                pool=15.0,
            ),
            transport=transport,
        )
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def _url(self) -> str:
        return "/chat/completions"

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tier: str = "router",
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for model in self._models[tier]:
            body: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                body["tools"] = tools
            if tool_choice is not None:
                body["tool_choice"] = tool_choice
            if max_tokens:
                body["max_tokens"] = max_tokens
            for attempt in range(self.max_retries + 1):
                try:
                    resp = self._client.post(self._url(), json=body)
                except httpx.TimeoutException as exc:
                    last_error = exc
                    time.sleep(min(self.retry_base_delay * (2**attempt), 8.0))
                    continue
                except httpx.TransportError as exc:  # 连接重置/网络抖动
                    last_error = exc
                    time.sleep(min(self.retry_base_delay * (2**attempt), 8.0))
                    continue
                if resp.status_code == 429 and _is_quota_exhausted(resp):
                    # 免费额度耗尽：换备用模型，不再空等
                    last_error = httpx.HTTPStatusError(
                        f"{model} 配额耗尽", request=resp.request, response=resp
                    )
                    break
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_error = httpx.HTTPStatusError(
                        f"模型接口限流/临时故障 {resp.status_code}", request=resp.request, response=resp
                    )
                    delay = self.retry_base_delay * (2**attempt)
                    if retry_after := resp.headers.get("retry-after"):
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    time.sleep(min(delay, 20.0))
                    continue
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError(f"模型网关全部重试/备用模型均失败: {last_error}") from last_error

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ModelGateway":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def build_gateway(settings: Settings | None = None) -> ModelGateway:
    settings = settings or load_settings()
    cfg: ModelConfig = settings.model
    api_key = os.environ.get(cfg.api_key_env, "")
    if not api_key:
        raise RuntimeError(f"缺少环境变量 {cfg.api_key_env}（LLM key 未配置）")
    base_url = cfg.base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
    return ModelGateway(
        api_key,
        base_url=base_url,
        router_model=cfg.router_model,
        deep_model=cfg.deep_model,
    )


def _dedupe(models: list[str]) -> list[str]:
    seen: list[str] = []
    for m in models:
        if m and m not in seen:
            seen.append(m)
    return seen


def _is_quota_exhausted(resp: httpx.Response) -> bool:
    try:
        data = resp.json()
        return "1305" in str(data.get("error", {}).get("code", ""))
    except Exception:
        return False
