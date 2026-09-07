"""Supervisor 两段路由：规则预筛（确定性、0 LLM）→ 便宜模型兜底。

设计原则（调研共识）：高频句式用规则直接命中；只有规则置信度低时才花一次
小模型调用，并把输出约束成 enum + JSON。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from advisor.graph.state import Intent
from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text, parse_json

CODE_PATTERN = re.compile(r"(?:(?:sh|sz|bj)\s*)?(\d{6})")

RISK_WORDS = ("测评", "风险承受", "问卷", "能承受", "风险测评", "适合什么产品", "开始测评", "我的风险")
PORTFOLIO_WORDS = ("持仓", "我的股票", "组合", "仓位", "我买了", "我持有", "我的基金")
QUOTE_WORDS = ("行情", "价格", "多少钱", "涨了", "跌了", "收盘", "报价", "现价", "今天多少")
RESEARCH_WORDS = ("分析", "研究", "基本面", "财务", "估值", "怎么样", "走势", "技术面", "值得", "深度", "体检", "看看", "评估", "报告")

VALID_INTENTS: set[str] = {"quote", "research", "portfolio", "risk", "chat"}


@dataclass
class RouteResult:
    intent: Intent
    symbols: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "rule"  # rule | llm | fallback


def _extract_symbols(text: str) -> list[str]:
    found: list[str] = []
    for m in CODE_PATTERN.finditer(text):
        code = m.group(1)
        if code not in found:
            found.append(code)
    return found


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def rule_route(text: str) -> RouteResult | None:
    """规则预筛。命中高风险意图（risk/portfolio）直接返回；普通行情/研究按关键词计分。
    符号提取与意图独立；无关键词但带 6 位代码 → quote（查行情）。"""
    lowered = text.lower()
    symbols = _extract_symbols(lowered)

    if _contains_any(lowered, RISK_WORDS):
        return RouteResult(intent="risk", symbols=symbols, confidence=0.95)
    if _contains_any(lowered, PORTFOLIO_WORDS):
        return RouteResult(intent="portfolio", symbols=symbols, confidence=0.95)

    score_quote = sum(1 for w in QUOTE_WORDS if w in lowered)
    score_research = sum(1 for w in RESEARCH_WORDS if w in lowered)
    if score_quote and not score_research:
        return RouteResult(intent="quote", symbols=symbols, confidence=0.9)
    if score_research and not score_quote:
        return RouteResult(intent="research", symbols=symbols, confidence=0.85)
    if score_quote and score_research:
        # 两种语义都有 → 低置信度，交 LLM 判断
        return RouteResult(intent="research", symbols=symbols, confidence=0.5)
    if symbols:
        return RouteResult(intent="quote", symbols=symbols, confidence=0.7)
    return None


ROUTE_SYSTEM = """你是投资助手的意图路由。只输出 JSON，不要多余文字：
{"intent": "quote|research|portfolio|risk|chat", "symbols": ["6位代码"], "confidence": 0.98}

意图定义：
- quote：只查价格/行情/涨跌；
- research：要基本面/财务/估值/技术面/新闻的深度分析；
- portfolio：问的是用户自己的持仓或组合；
- risk：风险测评/风险承受能力/问卷；
- chat：其他寒暄、常识、产品使用问题。

示例：
用户：贵州茅台现在多少钱 → {"intent": "quote", "symbols": ["600519"], "confidence": 0.98}
用户：看看我的持仓风险大不大 → {"intent": "portfolio", "symbols": [], "confidence": 0.97}
只输出上述 JSON 本身，不要解释，不要复述模板。
"""


def llm_route(gateway: ModelGateway, text: str) -> RouteResult:
    data = gateway.chat(
        [
            {"role": "system", "content": ROUTE_SYSTEM},
            {"role": "user", "content": f"用户：{text}"},
        ],
        tier="router",
        temperature=0.0,
        max_tokens=80,
    )
    text = message_text(data)
    try:
        raw = parse_json(text)
    except ValueError:
        # 模型偶发复述模板/占位符：按低置信度 chat 兜底，不把异常抛给上游
        return RouteResult(intent="chat", confidence=0.5, source="fallback")
    intent = raw.get("intent")
    if intent not in VALID_INTENTS:
        intent = "chat"
    symbols = [str(s) for s in (raw.get("symbols") or []) if str(s).isdigit()]
    try:
        confidence = float(raw.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6
    return RouteResult(
        intent=intent,
        symbols=symbols,
        confidence=max(0.0, min(confidence, 1.0)),
        source="llm",
    )


def route_request(text: str, gateway: ModelGateway | None = None) -> RouteResult:
    rule = rule_route(text)
    if rule is not None and rule.confidence >= 0.75:
        return rule
    if gateway is None:
        return rule or RouteResult(intent="chat", confidence=0.5, source="fallback")
    llm = llm_route(gateway, text)
    if llm.confidence >= 0.55 or rule is None:
        return llm
    return rule  # 规则存在但置信度略低，LLM 又没把握时仍用规则
