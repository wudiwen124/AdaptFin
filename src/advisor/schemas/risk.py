"""风险测评模型：问卷为数据驱动，评分/等级/约束全部走确定性规则。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    C1 = "C1"  # 保守型
    C2 = "C2"  # 稳健型
    C3 = "C3"  # 平衡型
    C4 = "C4"  # 积极型
    C5 = "C5"  # 激进型


class QuestionOption(BaseModel):
    text: str
    score: int = Field(ge=1, le=6)


class Question(BaseModel):
    id: str
    text: str
    options: list[QuestionOption] = Field(min_length=2)


QUESTIONNAIRE: list[Question] = [
    Question(
        id="q01",
        text="您的证券投资/基金投资经验有多久？",
        options=[
            QuestionOption(text="没有经验，刚开始了解", score=1),
            QuestionOption(text="不到 1 年", score=2),
            QuestionOption(text="1~3 年", score=4),
            QuestionOption(text="3 年以上", score=6),
        ],
    ),
    Question(
        id="q02",
        text="这笔资金预计多长时间内不需要动用？",
        options=[
            QuestionOption(text="1 年以内", score=1),
            QuestionOption(text="1~3 年", score=3),
            QuestionOption(text="3~5 年", score=5),
            QuestionOption(text="5 年以上", score=6),
        ],
    ),
    Question(
        id="q03",
        text="您能接受的阶段性最大亏损幅度大约是多少？",
        options=[
            QuestionOption(text="几乎不能接受亏损", score=1),
            QuestionOption(text="5% 以内", score=2),
            QuestionOption(text="10%~20%", score=4),
            QuestionOption(text="20% 以上", score=6),
        ],
    ),
    Question(
        id="q04",
        text="您的投资目标更接近以下哪种？",
        options=[
            QuestionOption(text="保本优先，收益随缘", score=1),
            QuestionOption(text="跑赢银行理财即可", score=2),
            QuestionOption(text="追求中长期稳健增值", score=4),
            QuestionOption(text="愿意承担波动追求较高收益", score=6),
        ],
    ),
    Question(
        id="q05",
        text="当持有的基金/股票短期下跌 10% 时，您通常会？",
        options=[
            QuestionOption(text="立即卖出止损", score=1),
            QuestionOption(text="非常焦虑，考虑减仓", score=2),
            QuestionOption(text="观察基本面后决定", score=4),
            QuestionOption(text="视为机会，可能加仓", score=6),
        ],
    ),
    Question(
        id="q06",
        text="您的金融知识水平更接近？",
        options=[
            QuestionOption(text="几乎不了解投资品种", score=1),
            QuestionOption(text="了解存款/理财等基础产品", score=2),
            QuestionOption(text="了解基金/股票的基本规则", score=4),
            QuestionOption(text="熟悉估值、技术面等分析方法", score=6),
        ],
    ),
    Question(
        id="q07",
        text="您的年收入/可投资资产中，计划投入风险资产的占比？",
        options=[
            QuestionOption(text="10% 以下", score=1),
            QuestionOption(text="10%~30%", score=3),
            QuestionOption(text="30%~60%", score=5),
            QuestionOption(text="60% 以上", score=6),
        ],
    ),
    Question(
        id="q08",
        text="您更偏好以下哪种资产特征？",
        options=[
            QuestionOption(text="波动小、收益确定性高", score=1),
            QuestionOption(text="以债/货基为主，少量权益", score=2),
            QuestionOption(text="股债平衡配置", score=4),
            QuestionOption(text="以高弹性权益为主", score=6),
        ],
    ),
    Question(
        id="q09",
        text="未来一年内是否有大额刚性支出计划（购房/留学等）？",
        options=[
            QuestionOption(text="有，且金额占可用资金大部分", score=1),
            QuestionOption(text="有可能，需保持高流动性", score=2),
            QuestionOption(text="暂无明确计划", score=5),
            QuestionOption(text="没有，且另有应急金", score=6),
        ],
    ),
    Question(
        id="q10",
        text="面对他人推荐的‘高收益’产品，您的态度是？",
        options=[
            QuestionOption(text="会心动并跟投", score=1),
            QuestionOption(text="先小额试试", score=3),
            QuestionOption(text="要求查看风险与底层资产", score=5),
            QuestionOption(text="直接拒绝，坚持自己的计划", score=6),
        ],
    ),
]


def level_for_score(score: int) -> RiskLevel:
    if score < 20:
        return RiskLevel.C1
    if score < 30:
        return RiskLevel.C2
    if score < 40:
        return RiskLevel.C3
    if score < 50:
        return RiskLevel.C4
    return RiskLevel.C5


class Constraints(BaseModel):
    """由风险等级推导的参考约束（示例框架，非投顾意见）。"""

    max_equity_ratio: float = Field(description="权益类资产占比上限，如 0.5")
    max_single_position: float = Field(description="单一标的仓位上限，如 0.15")
    horizon_hint: str = ""
    note: str = "仅供参考框架，不构成投资建议"


CONSTRAINTS: dict[RiskLevel, Constraints] = {
    RiskLevel.C1: Constraints(max_equity_ratio=0.3, max_single_position=0.05, horizon_hint="以流动性与保本为主"),
    RiskLevel.C2: Constraints(max_equity_ratio=0.5, max_single_position=0.08, horizon_hint="中低波动配置"),
    RiskLevel.C3: Constraints(max_equity_ratio=0.7, max_single_position=0.12, horizon_hint="股债平衡"),
    RiskLevel.C4: Constraints(max_equity_ratio=0.85, max_single_position=0.15, horizon_hint="权益为主"),
    RiskLevel.C5: Constraints(max_equity_ratio=1.0, max_single_position=0.2, horizon_hint="高弹性，需自行承受大波动"),
}


class RiskProfile(BaseModel):
    score: int = Field(ge=10, le=60)
    level: RiskLevel
    constraints: Constraints
    answered_at: datetime = Field(default_factory=datetime.now)
