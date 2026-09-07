"""P3-B：从用户原话做确定性记忆抽取（持仓变更 + 偏好事实）。

高频句式走规则（可单测、零 LLM 成本）；模糊表达暂不抽取，避免脏数据。
后续若要做“任意表达”抽取，再加 LLM 结构化输出 + 低置信度丢弃。
"""

from __future__ import annotations

import re

from advisor.schemas.user import Holding
from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text, parse_json

BUY_RE = re.compile(
    r"(?:买(?:入)?|买入|建仓|加仓|补仓|持有)(?:了)?\s*(?:(?P<qty>\d+)\s*(?:股|份|手))?\s*(?:(?:sh|sz))?(?P<code>\d{6})"
)
QTY_AFTER_CODE_RE = re.compile(r"(?:(?:sh|sz))?(?P<code>\d{6})\s*(?P<qty>\d+)\s*(?:股|份|手)")
SELL_RE = re.compile(r"(?:卖出|清仓|减仓|卖掉)\s*(?:(?:sh|sz))?(?P<code>\d{6})")

NEG_PREF_RE = re.compile(r"(?:我不喜欢|不喜欢|厌恶|讨厌|不碰|不考虑)\s*([^。；,!！?？，]{1,18})")
POS_PREF_RE = re.compile(r"(?:我比较偏好|比较偏好|我偏好|偏好|我关注|关注|感兴趣|看好)\s*([^。；,!！?？，]{1,18})")


def extract_memory_updates(text: str) -> tuple[list[Holding], list[str], list[str]]:
    """返回 (新增/变更持仓, 需删除的代码, 偏好事实)。"""
    holdings_map: dict[str, float | None] = {}
    for m in BUY_RE.finditer(text):
        code = m.group("code")
        holdings_map.setdefault(code, int(m.group("qty")) if m.group("qty") else None)
    for m in QTY_AFTER_CODE_RE.finditer(text):
        holdings_map[m.group("code")] = int(m.group("qty"))

    removed: list[str] = []
    for m in SELL_RE.finditer(text):
        code = m.group("code")
        if code in holdings_map:
            holdings_map.pop(code, None)
        removed.append(code)

    holdings = [Holding(symbol=code, qty=qty) for code, qty in holdings_map.items()]

    facts: list[str] = []
    for m in NEG_PREF_RE.finditer(text):
        target = m.group(1).strip().rstrip("的")
        if target:
            facts.append(f"用户不喜欢{target}")
    for m in POS_PREF_RE.finditer(text):
        target = m.group(1).strip().rstrip("的")
        if target:
            facts.append(f"用户偏好{target}")
    return holdings, removed, facts


LLM_PREF_TRIGGERS = ("打算", "希望", "想", "原则", "长期", "接受", "能承受", "不能接受", "可以承受")


def llm_extract_facts(gateway: ModelGateway | None, text: str) -> list[str]:
    """规则抓不住的自然表达 → 小模型结构化抽取，低置信度丢弃。"""
    if gateway is None or not any(t in text for t in LLM_PREF_TRIGGERS):
        return []
    system = (
        "你是用户画像抽取器。从用户一句话里抽取可长期记住的画像事实（投资期限/风险偏好/资金安排），"
        "不要抽取即时情绪。只输出 JSON: {\"facts\": [\"用户...\"], \"confidence\": 0.9}"
    )
    try:
        data = gateway.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": text[:200]},
            ],
            tier="router",
            max_tokens=120,
        )
        raw = parse_json(message_text(data))
        confidence = float(raw.get("confidence", 0.0))
        facts = [str(f).strip() for f in (raw.get("facts") or []) if str(f).strip()]
    except Exception:
        return []  # 超时/解析失败一律丢弃，不写脏记忆
    return facts if confidence >= 0.6 and len(facts) <= 3 else []
