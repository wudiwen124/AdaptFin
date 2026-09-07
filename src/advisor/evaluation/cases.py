"""黄金用例集（离线可跑，覆盖路由/合规/记忆/风险约束四类）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from advisor.schemas.risk import CONSTRAINTS, RiskLevel, RiskProfile

Category = Literal["routing", "compliance", "risk", "memory"]


@dataclass
class GoldenCase:
    id: str
    category: Category
    message: str
    expected_intent: str | None
    expected_contains: list[str] = field(default_factory=list)
    seed_risk_level: RiskLevel | None = None


GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        id="routing_quote_600519",
        category="routing",
        message="贵州茅台600519现在多少钱",
        expected_intent="quote",
        expected_contains=["不构成投资建议"],
    ),
    GoldenCase(
        id="routing_research_600519",
        category="routing",
        message="分析600519的基本面和技术面",
        expected_intent="research",
        expected_contains=["不构成投资建议"],
    ),
    GoldenCase(
        id="routing_portfolio_no_holdings",
        category="routing",
        message="看看我的持仓风险大不大",
        expected_intent="portfolio",
        expected_contains=["不构成投资建议"],
    ),
    GoldenCase(
        id="routing_risk_start",
        category="routing",
        message="我想做风险测评",
        expected_intent="risk",
        expected_contains=["1/10"],
    ),
    GoldenCase(
        id="routing_chat_greeting",
        category="routing",
        message="你好，介绍一下你能做什么",
        expected_intent="chat",
        expected_contains=[],
    ),
    GoldenCase(
        id="compliance_disclaimer_quote",
        category="compliance",
        message="600519今天收盘价是多少",
        expected_intent="quote",
        expected_contains=["不构成投资建议"],
    ),
    GoldenCase(
        id="risk_constraint_c1",
        category="risk",
        message="我的风险等级是多少",
        expected_intent="risk",
        expected_contains=["C1"],
        seed_risk_level=RiskLevel.C1,
    ),
    GoldenCase(
        id="risk_constraint_c5",
        category="risk",
        message="我的风险等级是多少",
        expected_intent="risk",
        expected_contains=["C5"],
        seed_risk_level=RiskLevel.C5,
    ),
    GoldenCase(
        id="memory_holding_record",
        category="memory",
        message="我买了100股510300",
        expected_intent="portfolio",
        expected_contains=["不构成投资建议"],
    ),
]


def make_profile(level: RiskLevel) -> RiskProfile:
    score = {RiskLevel.C1: 10, RiskLevel.C5: 60}[level]
    return RiskProfile(score=score, level=level, constraints=CONSTRAINTS[level])
