"""通用领域模型：证券代码、市场、周期。"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Market(str, Enum):
    CN_A = "cn_a"          # A 股股票
    CN_ETF = "cn_etf"      # 场内 ETF
    CN_INDEX = "cn_index"  # 指数（仅快照/特定代码）


class Period(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


_CODE_RE = re.compile(r"(?P<code>\d{6})")


class Symbol(BaseModel):
    """6 位证券代码 + 交易所 + 品种。不做现实世界里全市场代码的唯一性假设。"""

    code: str = Field(pattern=r"^\d{6}$")
    exchange: str = Field(pattern=r"^(sh|sz|bj)$")
    kind: str = Field(default="stock", pattern=r"^(stock|etf|index)$")
    name: str | None = None

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError(f"code 必须是 6 位数字: {v}")
        return v

    @classmethod
    def parse(cls, raw: str, *, kind: str | None = None, exchange: str | None = None) -> "Symbol":
        """解析 '600519' / 'sh600519' / '600519.SH' 等形式。

        交易所推断规则（A 股/ETF MVP 范围）：
        - 6/5/9 开头或 688/689 → sh
        - 4/8 开头 → bj
        - 其余（0/1/2/3）→ sz
        品种推断：sh 5 开头或 sz 1 开头按 ETF 处理。
        """
        text = raw.strip().lower().replace(".sh", "").replace(".sz", "").replace(".bj", "")
        m = _CODE_RE.search(text)
        if not m:
            raise ValueError(f"无法从 {raw!r} 解析证券代码")
        code = m.group("code")
        if exchange is None:
            if code[:3] in ("688", "689") or code[0] in ("5", "6", "9"):
                exchange = "sh"
            elif code[0] in ("4", "8"):
                exchange = "bj"
            else:
                exchange = "sz"
        if kind is None:
            kind = "etf" if (exchange == "sh" and code[0] == "5") or (exchange == "sz" and code[0] == "1") else "stock"
        return cls(code=code, exchange=exchange, kind=kind)

    @property
    def akshare_symbol(self) -> str:
        """akshare 多数接口使用的格式：sh600519 / sz000001。"""
        return f"{self.exchange}{self.code}"

    def __str__(self) -> str:  # noqa: D105
        return f"{self.exchange}{self.code}"
