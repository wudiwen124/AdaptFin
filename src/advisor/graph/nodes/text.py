"""消息类型兼容工具：langchain BaseMessage(dict) 统一处理。"""

from __future__ import annotations

import re
from typing import Any

ROLE_BY_TYPE = {
    "human": "user",
    "user": "user",
    "ai": "assistant",
    "assistant": "assistant",
    "system": "system",
}

TOOL_SOURCE_LABEL = {
    "get_realtime_quote": "行情数据源",
    "get_daily_kline": "历史行情数据源",
    "get_technical_indicators": "行情数据源",
    "get_financial_summary": "东方财富业绩报表",
    "get_company_profile": "公司资料数据源",
    "get_valuation": "估值数据源",
    "get_index_snapshot": "指数行情数据源",
    "get_recent_news": "东方财富公告",
}

_TOOL_NAME_RE = re.compile(r"get_[a-z_]+")


def message_role(msg: Any) -> str | None:
    if isinstance(msg, dict):
        return msg.get("role")
    role = getattr(msg, "role", None)
    if role:
        return role
    return ROLE_BY_TYPE.get(getattr(msg, "type", ""))


def message_content(msg: Any) -> str:
    if isinstance(msg, dict):
        content = msg.get("content") or ""
    else:
        content = getattr(msg, "content", None) or ""
    return str(content)


def to_openai_messages(messages: list[Any]) -> list[dict]:
    out = []
    for msg in messages:
        role = message_role(msg)
        if role is None:
            continue
        out.append({"role": role, "content": message_content(msg)})
    return out


def latest_user_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if message_role(msg) == "user" and message_content(msg).strip():
            return message_content(msg)
    return ""


def latest_text_with_role(messages: list[Any], role: str) -> str:
    for msg in reversed(messages):
        if message_role(msg) == role and message_content(msg).strip():
            return message_content(msg)
    return ""


def sanitize_user_facing(text: str) -> str:
    """把内部工具名/证据标签改写成用户可读的数据来源，不暴露 get_* 与调用细节。"""
    def _label(match: re.Match) -> str:
        return TOOL_SOURCE_LABEL.get(match.group(0), "数据源")

    # 去掉证据区内部标记整行/标签
    text = re.sub(r"【工具证据[^\n]*?】", "", text)
    text = re.sub(r"\[工具证据[^\]]*?\]", "", text)
    text = re.sub(r"【来源：?[^】]*?】", "", text)
    # get_xxx → 中文来源名；残余“来源：get_xxx”统一转换
    text = re.sub(r"来源[:：]?\s*get_[a-z_]+", lambda m: f"来源：{_label(re.search(r'get_[a-z_]+', m.group(0)))}", text)
    text = _TOOL_NAME_RE.sub(lambda m: _label(m), text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去掉开头的“结论摘要”标题
    text = re.sub(r"^\s*(?:\*\*结论摘要\*\*|【结论摘要】|#+\s*结论摘要|结论摘要)\s*[:：]?\s*\n?", "", text)
    return text.strip()
