"""P6-A：线程级实体注册表 + 指代消解（“它/这只/那个”→ 具体代码）。"""

from __future__ import annotations

import re

from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text, parse_json
from advisor.orchestration.resolver import NAME_INDEX

CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")

PRONOUN_MARKERS = ("它", "它们", "这只", "那只", "这支", "该股", "这个", "这些")
FOLLOWUP_HINTS = ("现在呢", "最近呢", "走势呢", "怎么样", "多少钱", "价格", "涨了", "跌了", "看看", "分析一下")

_CODE_TO_NAME = {code: name for name, code in NAME_INDEX.items()}


def explicit_codes(text: str) -> list[str]:
    return list(dict.fromkeys(CODE_RE.findall(text)))


def needs_resolution(text: str) -> bool:
    """当前句没有显式代码，且像省略主语的追问。"""
    if explicit_codes(text):
        return False
    return any(m in text for m in PRONOUN_MARKERS) or any(h in text for h in FOLLOWUP_HINTS)


def entity_payload(code: str, turn_no: int) -> dict:
    return {
        "code": code,
        "name": _CODE_TO_NAME.get(code) or code,
        "count": 1,
        "last_seen": turn_no,
    }


def resolve_target(
    gateway: ModelGateway | None,
    text: str,
    entities: list[dict],
) -> str | None:
    """从活跃实体里消解指代；多个候选时让 router 档小模型选一次。"""
    if not entities or not needs_resolution(text):
        return None
    active = sorted(entities, key=lambda e: (e.get("last_seen", 0), e.get("count", 0)), reverse=True)
    if len(active) == 1:
        return str(active[0]["code"])
    if gateway is None:
        return None
    return _llm_resolve(gateway, text, active)


def _llm_resolve(gateway: ModelGateway, text: str, candidates: list[dict]) -> str | None:
    options = "\n".join(f"{c['code']}（{c.get('name','')}）" for c in candidates[:8])
    system = "你是对话实体消解器。把省略主语的追问对应到最近提到的标的，只输出 JSON: {\"code\": \"600519\"}"
    try:
        data = gateway.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"候选：\n{options}\n用户追问：{text}"},
            ],
            tier="router",
            max_tokens=40,
        )
        code = str(parse_json(message_text(data)).get("code", ""))
        return code if code and any(c["code"] == code for c in candidates) else None
    except Exception:
        return None  # 解析失败不硬猜 → 上层反问
