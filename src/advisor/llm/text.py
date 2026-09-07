"""LLM 响应解析工具。"""

from __future__ import annotations

import json
from typing import Any


def message_text(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        return ""
    return content


def tool_calls_from(data: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return list(data["choices"][0]["message"].get("tool_calls") or [])
    except (KeyError, IndexError, TypeError):
        return []


def _extract_json_block(text: str) -> str:
    """兼容 ```json、单反引号、纯文本等包裹形式：直接截取第一个 { 到最后一个 }。"""
    cleaned = text.strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return cleaned
    return cleaned[start : end + 1]


def parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(_extract_json_block(text))
    except json.JSONDecodeError:
        raise ValueError(f"模型未返回合法 JSON: {text[:200]!r}")
