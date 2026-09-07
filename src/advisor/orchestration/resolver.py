"""名称→代码解析（P5-B）：先查本地索引，后续可扩展 akshare 全量股票表。"""

from __future__ import annotations

from advisor.datasources.demo import DEMO_NAMES

# 常用别名：长名称优先，避免“平安”命中“平安银行”歧义
NAME_INDEX: dict[str, str] = {
    "贵州茅台": "600519",
    "茅台": "600519",
    "中国平安": "601318",
    "平安银行": "000001",
    "宁德时代": "300750",
    "沪深300ETF": "510300",
    "创业板ETF": "159915",
}
for _code, _name in DEMO_NAMES.items():
    core = _name.replace("(演示)", "").strip()
    if core and core not in NAME_INDEX:
        NAME_INDEX[core] = _code


def resolve_names(text: str) -> list[str]:
    """返回文本中命中的代码（按名称长度降序匹配，避免子串歧义）。"""
    hits: list[str] = []
    for name in sorted(NAME_INDEX, key=len, reverse=True):
        if name in text and NAME_INDEX[name] not in hits:
            hits.append(NAME_INDEX[name])
    return hits


def known_names() -> list[str]:
    return sorted(set(NAME_INDEX))
