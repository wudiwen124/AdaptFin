"""P8 语义记忆：同义词组 + 子串打分的轻量召回（先离线，后叠加向量重排）。"""

from __future__ import annotations

# 语义同义词组：问法换了也能召回（group 内任意两个词分别出现在查询/记忆中即命中）
SYNONYM_GROUPS: list[tuple[str, ...]] = [
    ("红利", "高分红", "股息", "红利低波", "低波", "低波动"),
    ("长期", "三年", "长线", "拿三年", "五年"),
    ("频繁交易", "短线", "波段", "交易频率"),
    ("保守", "稳健", "低风险", "保本"),
    ("激进", "高风险", "高弹性", "进攻"),
    ("新能源", "光伏", "锂电", "电池", "风电"),
    ("消费", "白酒", "食品饮料", "家电"),
]


def score_facts(facts: list[str], query: str, limit: int = 5) -> list[tuple[str, int]]:
    """对每条 fact 打分：命中同义词组 +1、完整子串 +2；返回按分数降序。"""
    scored: list[tuple[str, int]] = []
    for fact in facts:
        score = 0
        if query in fact or fact in query:
            score += 2
        for group in SYNONYM_GROUPS:
            hit_query = any(alias in query for alias in group)
            hit_fact = any(alias in fact for alias in group)
            if hit_query and hit_fact:
                score += 1
        if score:
            scored.append((fact, score))
    scored.sort(key=lambda item: (-item[1], len(item[0])))
    return scored[:limit]
