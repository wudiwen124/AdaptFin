"""Risk Agent：问卷式 KYC，支持 查询 / 首次测评 / 重新测评 / 中途取消。

语义约定：
- 查询“我的风险等级/测评结果”只读，不写库；
- “重新测评/重做/再测一次”开启新问卷；完成前旧等级保持有效（原子替换）；
- 进行中回复“取消/退出/不测了”回到旧状态，不覆盖原画像；
- 评分永远走规则（score_answers）；LLM 只做自由文本→选项的映射兜底。
"""

from __future__ import annotations

from advisor.graph.nodes.text import latest_user_text
from advisor.graph.state import AssistantState
from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text, parse_json
from advisor.schemas.risk import QUESTIONNAIRE
from advisor.store import ProfileStore
from advisor.tools.risk_model import score_answers

START_HINT = ("测评", "问卷", "开始", "测一下", "测试", "评估一下风险")
REDO_WORDS = (
    "重新测评", "重新做", "重做", "重新测", "重测", "再做一次", "再测一次",
    "更新测评", "换一个风险", "重选", "改一下风险", "重新评估风险",
)
CANCEL_WORDS = ("取消", "退出", "算了", "不测了", "不做了", "停止测评", "先不测")


def _profile_summary(profile) -> str:
    return (
        f"您当前的测评结果：风险等级 {profile.level.value}，总分 {profile.score}。\n"
        f"参考约束：权益类 ≤{profile.constraints.max_equity_ratio:.0%}，"
        f"单一标的 ≤{profile.constraints.max_single_position:.0%}；{profile.constraints.horizon_hint}。\n"
        "想调整的话，回复“重新测评”即可重新作答；期间原等级保持有效。\n"
        "以上为参考框架，不构成投资建议。"
    )


def _question_prompt(q_index: int, *, redo: bool = False) -> str:
    q = QUESTIONNAIRE[q_index]
    lines = [f"第 {q_index + 1}/{len(QUESTIONNAIRE)} 题：{q.text}"]
    lines += [f"{i + 1}. {opt.text}" for i, opt in enumerate(q.options)]
    if redo:
        lines.append("（重新测评中：回复“取消”可保留原等级退出）")
    lines.append("请回复选项编号（如 1）或直接描述你的情况。")
    return "\n".join(lines)


def _match_option(q, text: str) -> int | None:
    """返回选项 score；纯规则先行。"""
    text = text.strip().lower()
    if text in {str(i) for i in range(1, len(q.options) + 1)}:
        return q.options[int(text) - 1].score
    for opt in q.options:
        if opt.text and opt.text in text:
            return opt.score
    return None


def _llm_match_option(gateway: ModelGateway, q, text: str) -> int:
    options = "\n".join(f"{i + 1}. {o.text}" for i, o in enumerate(q.options))
    try:
        data = gateway.chat(
            [
                {"role": "system", "content": "把用户回答匹配到最接近的选项，只输出 JSON: {\"option\": 1}"},
                {"role": "user", "content": f"题目：{q.text}\n选项：\n{options}\n用户回答：{text}"},
            ],
            tier="router",
            max_tokens=30,
        )
        raw = parse_json(message_text(data))
    except Exception:  # 超时/网络/解析失败都按“无法映射”处理 → 原题重问
        return -1
    idx = int(raw.get("option", 1))
    idx = max(1, min(idx, len(q.options)))
    return q.options[idx - 1].score


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _stored_risk(store: ProfileStore | None, user_id: str):
    if store is None or not user_id:
        return None
    profile = store.get_profile(user_id)
    return profile.risk if profile else None


def risk_node(
    state: AssistantState,
    *,
    gateway: ModelGateway,
    store: ProfileStore | None = None,
) -> dict:
    user_id = state.get("user_id", "")
    profile = state.get("risk_profile")
    text = latest_user_text(state.get("messages") or [])
    q_index = state.get("q_index", 0)  # 已展示题数（0=未开始）
    scores = list(state.get("q_scores") or [])

    # ---- 已有画像：查询 vs 重做 ----
    if profile is not None:
        if _contains_any(text, REDO_WORDS):
            return {
                "q_index": 1,
                "q_scores": [],
                "risk_profile": None,
                "risk_done": False,
                "risk_dirty": False,
                "final_answer": _question_prompt(0, redo=True),
            }
        return {
            "risk_done": True,
            "final_answer": _profile_summary(profile),
        }

    # ---- 进行中：取消 ----
    if q_index > 0 and _contains_any(text, CANCEL_WORDS):
        old = _stored_risk(store, user_id)
        if old is not None:
            msg = f"已取消本次测评，原风险等级 {old.level.value} 保持不变。"
        else:
            msg = "已取消本次测评。随时说“开始测评”重新开始。"
        return {
            "q_index": 0,
            "q_scores": [],
            "risk_done": True,
            "final_answer": msg,
        }

    # ---- 未开始：引导或开始 ----
    if q_index == 0:
        if not (_contains_any(text, START_HINT) or _contains_any(text, REDO_WORDS)):
            return {
                "final_answer": "好的，我们先花 1 分钟做一次风险测评（10 题）。随时回复“开始测评”即可。",
                "risk_done": False,
            }
        return {
            "q_index": 1,
            "q_scores": [],
            "final_answer": _question_prompt(0),
            "risk_done": False,
        }

    # ---- 作答中 ----
    current = q_index - 1  # 用户正在回答的题号（0 基）
    q = QUESTIONNAIRE[current]
    score = _match_option(q, text)
    if score is None:
        score = _llm_match_option(gateway, q, text)
    if score is None or score < 1:
        return {
            "q_index": q_index,  # 题目不变，请用户重新作答
            "q_scores": scores,
            "final_answer": f"没太看懂您的回答，请重新选择：\n{_question_prompt(current)}",
            "risk_done": False,
        }
    scores.append(score)

    if len(scores) < len(QUESTIONNAIRE):
        return {
            "q_index": q_index + 1,
            "q_scores": scores,
            "final_answer": _question_prompt(q_index),
            "risk_done": False,
        }

    answers = {q_.id: s for q_, s in zip(QUESTIONNAIRE, scores)}
    risk = score_answers(answers)
    old = _stored_risk(store, user_id)
    if old is not None and old.level != risk.level:
        headline = f"测评完成 ✅ 风险等级已由 {old.level.value} 更新为 {risk.level.value}（总分 {risk.score}/60）"
    else:
        headline = f"测评完成 ✅ 总分 {risk.score}/60，风险等级 {risk.level.value}"
    return {
        "q_scores": scores,
        "risk_profile": risk,
        "risk_done": True,
        "risk_dirty": True,  # 只有这里才是“新测评结果”，Memory Writer 才写库
        "final_answer": (
            f"{headline}。\n"
            f"参考约束：权益类 ≤{risk.constraints.max_equity_ratio:.0%}，"
            f"单一标的 ≤{risk.constraints.max_single_position:.0%}；{risk.constraints.horizon_hint}。\n"
            "画像已更新，之后的分析都会按新约束生成；历史测评记录保留可查。\n"
            "以上为参考框架，不构成投资建议。"
        ),
    }


def after_risk(state: AssistantState) -> str:
    return "memory_writer" if state.get("risk_done") else "__end__"
