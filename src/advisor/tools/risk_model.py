"""风险问卷评分：输入选项得分映射，输出 RiskProfile（全部确定性规则）。"""

from __future__ import annotations

from collections.abc import Mapping

from advisor.schemas.risk import CONSTRAINTS, QUESTIONNAIRE, RiskProfile, level_for_score

_QUESTION_IDS = {q.id for q in QUESTIONNAIRE}


def score_answers(answers: Mapping[str, int]) -> RiskProfile:
    """answers: {question_id: 所选选项的 score(1~6)}。

    校验：题号完整、无未知题号、分数在 1~6（在真实 UI 中由选项分值产生）。
    """
    provided = set(answers)
    if provided != _QUESTION_IDS:
        missing = sorted(_QUESTION_IDS - provided)
        unknown = sorted(provided - _QUESTION_IDS)
        raise ValueError(f"问卷答案不完整或包含未知题号: missing={missing}, unknown={unknown}")
    if any(not isinstance(v, int) or not 1 <= v <= 6 for v in answers.values()):
        raise ValueError("每题分值必须在 1~6 之间")
    score = sum(answers.values())
    level = level_for_score(score)
    return RiskProfile(score=score, level=level, constraints=CONSTRAINTS[level])
