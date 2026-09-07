"""用户画像与持仓（长期记忆 Store 的结构化形态）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from advisor.schemas.risk import RiskProfile


class Holding(BaseModel):
    symbol: str
    name: str | None = None
    qty: float | None = None  # 用户只说“买了 510300”没给数量时允许未知
    cost: float | None = None
    updated_at: datetime = Field(default_factory=datetime.now)


class UserProfile(BaseModel):
    user_id: str
    risk: RiskProfile | None = None
    prefs: dict[str, Any] = Field(default_factory=dict)  # interest/horizon/style_note...
    holdings: list[Holding] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
