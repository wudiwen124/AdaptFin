"""研究输出模型：Claim 四分类（调研自 wyh22），供 Auditor 做确定性审计。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClaimKind(str, Enum):
    FACT = "FACT"                  # 可直接由工具/数据支持的陈述
    CALCULATION = "CALCULATION"    # 基于已知输入的可复算派生值
    INFERENCE = "INFERENCE"        # 从证据形成的解释性判断
    CONDITIONAL = "CONDITIONAL"    # 仅在触发条件成立时成立的情景


class Claim(BaseModel):
    text: str
    kind: ClaimKind
    source: str | None = Field(
        default=None,
        description="工具名 + 数据日期，如 'akshare:quote 600519@2026-09-04'",
    )


class ResearchReport(BaseModel):
    """Research Agent（fan-in 后）的产出，进入 Advisor 前必须全部带 claims。"""

    symbol: str
    summary: str
    claims: list[Claim] = Field(default_factory=list)
    as_of: str | None = None


class EvidenceRecord(BaseModel):
    """工具调用的一次原始证据：Auditor 用它对最终回答做数字/来源核对。"""

    tool: str
    args: dict = Field(default_factory=dict)
    output: str = ""
    source: str | None = None       # 数据源（akshare/demo/...）
    data_as_of: str | None = None   # 数据日期
