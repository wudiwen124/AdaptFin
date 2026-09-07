"""Auditor（P3-A 证据级）：免责/指令性表述/数字出处/PIT 日期检查 + 有界回修。

检查全部确定性实现：
1. 免责声明存在；
2. 无“买入/卖出/加仓/减仓”指令性表述；
3. 最终回答中的每个小数（如 33.89、42.37）必须能在工具原始输出或风险画像里找到；
4. 回答中出现的具体日期不能晚于/超出工具数据日期集合（PIT 守卫）。
"""

from __future__ import annotations

import re
from datetime import date

from langchain_core.messages import SystemMessage

from advisor.graph.nodes.text import message_content, message_role
from advisor.graph.state import AssistantState

DISCLAIMER = "\n\n⚠️ 以上内容仅为研究辅助信息，不构成投资建议；市场有风险，投资需谨慎。"
FORBIDDEN = re.compile(r"(?:建议|立刻|马上|抓紧|赶紧|立即|尽快|现在就去).{0,6}(?:买入|卖出|加仓|减仓|清仓|抄底|重仓)")
DECIMAL_RE = re.compile(r"(?<!\d)(\d+\.\d+)(?!\d)")
DATE_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?")


def _decimal_set(text: str) -> set[str]:
    return {m for m in DECIMAL_RE.findall(text)}


def _date_set(text: str) -> set[str]:
    out = set()
    for y, m, d in DATE_RE.findall(text):
        out.add(f"{y}-{int(m):02d}" + (f"-{int(d):02d}" if d else ""))
    return out


def _allowed_text(state: AssistantState) -> str:
    """允许出现在最终回答里的数字/日期来源：工具原始输出 + 风险画像 + 问题原文。"""
    parts: list[str] = []
    if as_of := state.get("as_of_date"):
        parts.append(as_of)
    for rec in state.get("tool_observations") or []:
        parts.append(rec.output)
        if rec.data_as_of:
            parts.append(rec.data_as_of)
    for report in state.get("research_results") or []:
        parts.append(report.summary)
    if ctx := state.get("agent_context"):
        parts.append(ctx)
    risk = state.get("risk_profile")
    if risk is not None:
        parts.append(risk.model_dump_json())
    for msg in state.get("messages") or []:
        if message_role(msg) == "user":
            parts.append(message_content(msg))
    return "\n".join(parts)


def auditor_node(state: AssistantState, max_rounds: int = 2) -> dict:
    final = state.get("final_answer") or ""
    allowed = _allowed_text(state)
    issues: list[str] = []

    if state.get("intent") != "chat" and "不构成投资建议" not in final:
        final = final.rstrip() + DISCLAIMER
        issues.append("缺少免责声明（已自动补齐）")
    if FORBIDDEN.search(final):
        issues.append("出现指令性买卖表述")

    final_decimals = _decimal_set(final)
    if final_decimals:
        allowed_decimals = _decimal_set(allowed)
        missing = sorted(final_decimals - allowed_decimals)
        if missing:
            issues.append(f"以下数字在工具证据/画像中不存在: {', '.join(missing[:6])}")

    evidence_dates = _date_set(allowed)
    if evidence_dates:
        unknown_dates = sorted(_date_set(final) - evidence_dates)
        if unknown_dates:
            issues.append(f"回答中出现证据外的日期: {', '.join(unknown_dates[:4])}")

    as_of = state.get("as_of_date")
    if as_of:
        late = _late_evidence(state.get("tool_observations") or [], as_of)
        if late:
            issues.append(f"工具数据晚于研究截止日 {as_of}: {', '.join(late[:4])}")

    if not issues:
        return {"final_answer": final, "audit_round": state.get("audit_round", 0), "audit_issue": None}
    if state.get("audit_round", 0) >= max_rounds:
        return {"final_answer": final, "audit_round": state.get("audit_round", 0), "audit_issue": None}

    instruction = "请按审计意见修订上一条回答：" + "；".join(issues) + "。删掉无法由【证据区】支撑的数字，或明确标注为推测。"
    return {
        "final_answer": final,
        "audit_round": state.get("audit_round", 0) + 1,
        "audit_issue": "; ".join(issues),
        "messages": [SystemMessage(content="审计提示：" + instruction)],
    }


def _late_evidence(observations: list, as_of: str) -> list[str]:
    out = []
    for rec in observations:
        raw = getattr(rec, "data_as_of", None)
        if raw and str(raw)[:10] > as_of:
            out.append(f"{rec.tool}@{str(raw)[:10]}")
        # 公告/财务等时间字段埋在输出 JSON 里（published_at / 报告期），逐条扫描
        if getattr(rec, "tool", "") in {"get_recent_news", "get_financial_summary"} and getattr(rec, "output", ""):
            for found in _date_set(str(getattr(rec, "output", ""))):
                if found[:10] > as_of:
                    out.append(f"{rec.tool}@{found[:10]}")
    return out


def after_audit(state: AssistantState) -> str:
    if state.get("audit_issue") and state.get("audit_round", 0) <= 2:
        return "advisor"
    return "memory_writer"
