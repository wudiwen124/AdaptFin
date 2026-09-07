"""通用 Agent 工具循环：LLM 决定 → 执行工具 → 观察，直到不再调用工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text, tool_calls_from
from advisor.schemas.research import EvidenceRecord


@dataclass
class AgentRun:
    text: str = ""
    tool_calls: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    observations: list[EvidenceRecord] = field(default_factory=list)  # 原始工具证据


def openai_tool_schema(tool: BaseTool) -> dict[str, Any]:
    schema = (
        tool.args_schema.model_json_schema()
        if tool.args_schema is not None
        else {"type": "object", "properties": {}}
    )
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user" and msg.get("content"):
            return str(msg["content"])
    return ""


def run_tool_agent(
    gateway: ModelGateway,
    *,
    system_prompt: str,
    user_text: str,
    tools: list[BaseTool],
    tier: str = "deep",
    max_steps: int = 4,
) -> AgentRun:
    """bounded ReAct 循环：每个 Agent 可自主决定是否/何时调用工具。"""
    run = AgentRun()
    schemas = [openai_tool_schema(t) for t in tools]
    by_name = {t.name: t for t in tools}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        data = gateway.chat(messages, tier=tier, temperature=0.0, tools=schemas, max_tokens=900)
        calls = tool_calls_from(data)
        text = message_text(data)
        if not calls:
            run.text = text
            return run
        messages.append({"role": "assistant", "content": text or None, "tool_calls": calls})
        for call in calls:
            try:
                fn = call["function"]
                name = fn.get("name", "")
                args = json.loads(fn.get("arguments") or "{}")
                tool = by_name.get(name)
                if tool is None:
                    observation = json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
                else:
                    observation = tool.func(**args) if isinstance(args, dict) else str(tool.func(args))
            except Exception as exc:  # 工具执行失败也作为观察返回，不中断循环
                observation = json.dumps({"error": str(exc)}, ensure_ascii=False)
            run.tool_calls.append(name)
            run.observations.append(
                EvidenceRecord(
                    tool=name,
                    args=args,
                    output=observation,
                    **_meta_fields(observation),
                )
            )
            run.sources.append(f"{name}({args})")
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": observation})

    # 达到轮次上限：再问一次让模型收敛
    data = gateway.chat(messages, tier=tier, temperature=0.0, max_tokens=900)
    run.text = message_text(data)
    return run


def _meta_fields(observation: str) -> dict[str, str | None]:
    """从工具输出 JSON 中抽取 source/data_as_of（尽力而为，解析失败不报错）。"""
    try:
        payload = json.loads(observation)
    except (json.JSONDecodeError, TypeError):
        return {}
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return {}
    meta = payload.get("meta")
    if isinstance(meta, dict):
        return {
            "source": str(meta.get("source") or "") or None,
            "data_as_of": str(meta.get("data_as_of") or "") or None,
        }
    return {}
