import pytest

from advisor.schemas.risk import QUESTIONNAIRE, RiskLevel
from advisor.tools.risk_model import score_answers


def _all_score(value: int) -> dict[str, int]:
    return {q.id: value for q in QUESTIONNAIRE}


def test_extreme_scores():
    c1 = score_answers(_all_score(1))
    assert c1.score == 10
    assert c1.level == RiskLevel.C1
    assert c1.constraints.max_equity_ratio == 0.3

    c5 = score_answers(_all_score(6))
    assert c5.score == 60
    assert c5.level == RiskLevel.C5
    assert c5.constraints.max_equity_ratio == 1.0


def test_mid_boundaries():
    assert score_answers(_all_score(2)).level == RiskLevel.C2
    assert score_answers(_all_score(3)).level == RiskLevel.C3
    assert score_answers(_all_score(4)).level == RiskLevel.C4
    assert score_answers(_all_score(5)).level == RiskLevel.C5
    mixed = _all_score(4)
    mixed["q01"] = 5  # 41 分：C4 上边界内
    assert score_answers(mixed).level == RiskLevel.C4


def test_incomplete_answers_raise():
    answers = _all_score(3)
    answers.pop("q01")
    with pytest.raises(ValueError, match="不完整"):
        score_answers(answers)


def test_invalid_score_raises():
    answers = _all_score(3)
    answers["q01"] = 7
    with pytest.raises(ValueError, match="1~6"):
        score_answers(answers)
