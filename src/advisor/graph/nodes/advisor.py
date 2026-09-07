"""Advisor：画像注入 + 证据引用 + 合规话术的统一合成节点。"""

from __future__ import annotations

from advisor.graph.state import AssistantState
from advisor.graph.nodes.text import latest_text_with_role, latest_user_text, sanitize_user_facing
from advisor.llm.client import ModelGateway
from advisor.llm.text import message_text

ADVISOR_SYSTEM = """你是智能投顾助手的“参考意见”合成器（研究辅助性质，不是持牌投顾）。
规则（按优先级）：
1. 合规：不预测收益；不给出“买入/卖出/加仓/减仓/清仓”指令性表述；只给研究视角、参考结构与关注点。结尾必须包含“不构成投资建议”。
2. 个性化：如果提供了风险画像，用它的权益/单标的仓位上限与期限来评估适配度；未测评则说明“完成 10 题风险测评后可获得个性化约束”，仍可给概括性分析。
3. 引用：凡涉及数字，只允许来自【证据区】的工具输出；证据缺失就写“暂无该数据”。【证据区】没有的信息不得编造。**回答中禁止出现 get_ 开头的内部工具名**；要写来源时用“东方财富公告 / 东方财富业绩报表 / 行情数据源”这类用户可读名称。
4. 结构：结论摘要 → 证据（来源与数据日期）→ 与画像的适配 → 风险提示 → 免责声明。中文回答，700 字以内。"""

CHAT_SYSTEM = """你是 AdaptFin 的对话助手。
规则：
1. 回应用户的寒暄/闲聊/能力询问时自然、简短、友好；用户问“你好”就用问候回应并一句话介绍你能做什么。
2. 除非用户主动问行情/研究/持仓/投资问题，否则不套用投顾报告模板、不主动讨论仓位/风险。
3. 如果用户开始问金融问题，提示可以帮他做风险测评/查行情/研究个股，并结束回复。
4. 禁止出现 get_ 开头的内部工具名。"""


def _evidence(state: AssistantState) -> str:
    blocks = []
    if ctx := state.get("agent_context"):
        blocks.append(f"行情/研究结论：\n{ctx}")
    for report in state.get("research_results") or []:
        blocks.append(f"研究标的 {report.symbol}（截止 {report.as_of}）：\n{report.summary}")
    for rec in state.get("tool_observations") or []:
        args = rec.args if isinstance(rec.args, dict) else {}
        blocks.append(f"[工具证据 {rec.tool}({args}) source={rec.source} as_of={rec.data_as_of}]\n{rec.output[:500]}")
    if blocks:
        return "\n\n".join(blocks)
    return "（暂无工具证据，只能做通用说明）"


def _risk_text(state: AssistantState) -> str:
    p = state.get("risk_profile")
    if p is None:
        return "用户尚未完成风险测评"
    return (
        f"等级 {p.level.value}，总分 {p.score}，权益上限 {p.constraints.max_equity_ratio:.0%}，"
        f"单标的 {p.constraints.max_single_position:.0%}，期限提示：{p.constraints.horizon_hint}"
    )


def _conversation_context(state: AssistantState, limit: int = 6) -> str:
    """最近几轮对话（含助手历史回答），用于“那 510300 呢”类省略追问。"""
    entries: list[str] = []
    for msg in reversed(state.get("messages") or []):
        role = "user" if hasattr(msg, "type") and getattr(msg, "type", "") == "human" else getattr(msg, "type", None)
        if role not in {"human", "ai"}:
            continue
        content = str(getattr(msg, "content", "") or "")
        if content.strip():
            entries.append(f"{'用户' if role == 'human' else '助手'}: {content[:400]}")
        if len(entries) >= limit:
            break
    return "\n".join(reversed(entries)) or "（无）"


def _latest_user_text(state: AssistantState) -> str:
    return latest_user_text(state.get("messages") or [])


def advisor_node(state: AssistantState, *, gateway: ModelGateway) -> dict:
    # 固定事实：吴帝文 → AdaptFin 开发者（确定性优先，不依赖模型）
    if state.get("intent") == "chat" and "吴帝文" in _latest_user_text(state):
        return {"final_answer": "吴帝文是 AdaptFin 的开发者。"}

    audit_note = latest_text_with_role(state.get("messages") or [], "system")
    audit_notes = [audit_note] if audit_note and "指令性表述" in audit_note else []
    extra = "\n".join(audit_notes)
    gap = state.get("query_gap")
    memory = state.get("user_memory")
    context = _conversation_context(state)
    gap_line = f"⚠️ 本轮需要澄清：{gap}\n\n" if gap else ""
    user_prompt = (
        f"{gap_line}"
        f"用户问题：{_latest_user_text(state)}\n\n"
        f"风险画像：{_risk_text(state)}\n\n"
        f"【用户记忆】\n{memory or '（暂无长期记忆）'}\n\n"
        f"【最近对话】\n{context}\n\n"
        f"【证据区】\n{_evidence(state)}\n"
        f"{('审计提示：' + extra) if extra else ''}"
    )
    system_prompt = CHAT_SYSTEM if state.get("intent") == "chat" else ADVISOR_SYSTEM
    data = gateway.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tier="deep",
        temperature=0.2,
        max_tokens=900,
    )
    return {"final_answer": sanitize_user_facing(message_text(data))}
