"""测试/评测用 Fake LLM：离线、确定性、可脚本化。"""

from __future__ import annotations

import json
import re
from typing import Any


def _system(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return str(m.get("content") or "")
    return ""


def _user(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


class FakeGateway:
    """按消息内容返回确定性结果。queue 用于脚本化工具调用测试。"""

    def __init__(self, queue: list[dict[str, Any]] | None = None) -> None:
        self.queue = list(queue or [])
        self.calls: list[tuple[str, int]] = []  # (tier, n_messages)

    def _respond(self, tier: str, messages: list[dict]) -> dict[str, Any]:
        system = _system(messages)
        user = _user(messages)
        self.calls.append((tier, len(messages)))
        if "意图定义" in system:
            if any(w in user for w in ("测评", "风险")):
                intent = "risk"
            elif any(w in user for w in ("持仓", "组合", "我买了")):
                intent = "portfolio"
            elif "分析" in user or "研究" in user or "怎么样" in user:
                intent = "research"
            elif any(w in user for w in ("价格", "多少钱", "行情")):
                intent = "quote"
            else:
                intent = "chat"
            codes = re.findall(r"(?<!\d)(\d{6})(?!\d)", user)
            return self._content(json.dumps({"intent": intent, "symbols": codes, "confidence": 0.99}, ensure_ascii=False))
        if "把用户回答匹配" in system:
            return self._content('{"option": 1}')
        if "实体消解器" in system:
            if "600519" in user:
                code = "600519"
            else:
                codes = re.findall(r"(?<!\d)(\d{6})(?!\d)", user)
                code = codes[0] if codes else ""
            return self._content(json.dumps({"code": code}, ensure_ascii=False))
        if "用户画像抽取器" in system:
            if "打算" in user or "接受" in user or "长期" in user:
                facts = ["用户打算长期持有，可接受 20% 左右回撤"]
            else:
                facts = []
            return self._content(json.dumps({"facts": facts, "confidence": 0.9}, ensure_ascii=False))
        if "你是行情查询专员" in system:
            codes = re.findall(r"(?<!\d)(\d{6})(?!\d)", user)
            has_tool_result = any(m.get("role") == "tool" for m in messages)
            if codes and not has_tool_result:
                return FakeGateway.tool_call("get_realtime_quote", {"symbol": codes[0]})
            return self._content("（演示）行情工具调用结果正常，价格来自 demo 源。")
        if "基本面分析师" in system or "技术面分析师" in system or "资讯/情绪分析师" in system:
            return self._content("（演示）分析师结论：基于工具返回的数据，暂无异常。")
        if "智能投顾助手的“参考意见”合成器" in system:
            return self._content("（演示）以下为参考分析，请以工具数据为准。风险提示：市场有波动。不构成投资建议。")
        if "AdaptFin 的对话助手" in system:
            return self._content("（演示）你好！我是 AdaptFin，可以帮你查行情、研究个股、做风险测评。")
        return self._content("（演示）已收到，请补充标的信息。")

    @staticmethod
    def _content(text: str) -> dict[str, Any]:
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}

    @staticmethod
    def tool_call(name: str, args: dict, call_id: str = "call_1") -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                            }
                        ],
                    }
                }
            ]
        }

    def chat(self, messages: list[dict], *, tier: str = "router", **_: Any) -> dict[str, Any]:
        if self.queue:
            return self.queue.pop(0)
        return self._respond(tier, messages)
