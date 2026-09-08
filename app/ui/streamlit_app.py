"""Streamlit 演示 UI（P4-2）。

启动：
    streamlit run app/ui/streamlit_app.py

包含：聊天（走 LangGraph 主图）、风险测评表单（10 题，走同一套评分规则）、持仓管理。
"""

from __future__ import annotations

import html as _html
import re

import streamlit as st
from langchain_core.messages import HumanMessage

from advisor.config import load_settings
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.graph.nodes.extract import extract_memory_updates
from advisor.llm.client import build_gateway
from advisor.schemas.risk import QUESTIONNAIRE
from advisor.store import ProfileStore
from advisor.tools.risk_model import score_answers


@st.cache_resource
def get_resources():
    settings = load_settings()
    gateway = build_gateway(settings)
    router = build_default_router(settings)
    store = ProfileStore(settings.store.db_path, checkpoint_db_path=settings.store.checkpoint_db_path)
    graph = build_app(gateway=gateway, router=router, store=store, settings=settings)
    return graph, store


def _ask(graph, user_id: str, thread: str, text: str) -> dict:
    return graph.invoke(
        {"user_id": user_id, "messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread}},
    )


def _md_escape(text: str) -> str:
    """轻量转义 + 支持加粗/换行/无序列表，渲染成气泡内 HTML。"""
    esc = _html.escape(text)
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"(?m)^\s*[-*]\s+", "• ", esc)
    return esc.replace("\n", "<br>")


def _bubble(role: str, content: str) -> str:
    row = "msg-row-user" if role == "user" else "msg-row-assistant"
    bubble = "bubble-user" if role == "user" else "bubble-assistant"
    return f'<div class="msg-row {row}"><div class="bubble {bubble}">{_md_escape(content)}</div></div>'


def main() -> None:
    st.set_page_config(page_title="AdaptFin", page_icon="assets/adaptfin.png", layout="wide")
    graph, store = get_resources()

    with st.sidebar:
        st.title("投顾助手控制台")
        existing = store.list_user_ids()
        picker_options = ["➕ 新用户"] + existing
        picked = st.selectbox("选择已有用户 / 新建", picker_options, key="user_picker")
        if picked == "➕ 新用户" or not existing:
            user_id = st.text_input("新用户 ID", value="", key="new_user_id")
            if not user_id:
                user_id = "demo_user"
        else:
            user_id = picked
        thread = f"ui_{user_id}"
        st.caption(f"当前用户：{user_id}（会话线程 ui_{user_id}）")
        st.divider()

        st.subheader("当前画像")
        profile = store.get_profile(user_id)
        if profile and profile.risk:
            r = profile.risk
            st.metric("风险等级", r.level.value)
            st.caption(
                f"总分 {r.score} · 权益上限 {r.constraints.max_equity_ratio:.0%} · "
                f"单标的 {r.constraints.max_single_position:.0%}"
            )
        else:
            st.info("尚未测评，先做 10 题风险测评")

        st.subheader("持仓管理")
        holding_text = st.text_area(
            "一句话操作，如：\n买入 100股 510300\n卖出 600519",
            height=110,
        )
        if st.button("应用持仓变更", use_container_width=True):
            holdings, removed, _ = extract_memory_updates(holding_text)
            for h in holdings:
                store.add_holding(user_id, h)
            for code in removed:
                store.remove_holding(user_id, code)
            st.success(f"已更新：+{len(holdings)} 条，-{len(removed)} 条")
            st.rerun()

        current = store.get_holdings(user_id)
        if current:
            st.dataframe(
                [{"代码": h.symbol, "数量": h.qty if h.qty else "未知"} for h in current],
                use_container_width=True,
                hide_index=True,
            )

        history = store.risk_history(user_id) if user_id else []
        if history:
            st.caption("测评历史：" + " → ".join(f"{h['level']}({h['score']})" for h in history))
        st.divider()
        with st.expander("数据管理（危险操作）"):
            if existing:
                del_user = st.selectbox("选择要删除的用户", existing, key="del_picker")
                confirm_del = st.checkbox(f"我确认删除 {del_user}（含画像/持仓/记忆/测评历史/对话）", key="confirm_del")
                if st.button("删除选中用户", disabled=not confirm_del, use_container_width=True):
                    store.delete_user(del_user)
                    st.success(f"已删除用户 {del_user}")
                    st.rerun()
            confirm_all = st.checkbox("我确认清空所有用户", key="confirm_all")
            if st.button("清空所有用户", disabled=not confirm_all, use_container_width=True):
                n = store.clear_all_users()
                st.success(f"已清空 {n} 个用户")
                st.rerun()
        st.caption("研究辅助 / 教育模拟用途，不构成投资建议。")

    st.markdown(
        """
        <style>
        .block-container { max-width: 940px !important; padding-top: 1.2rem; }
        h2.chat-title { text-align: center; font-weight: 600; margin-top: 2.4rem; margin-bottom: 0.15rem; }
        .chat-sub { text-align: center; color: #8a8f98; font-size: 0.9rem; margin-bottom: 1.2rem; }
        .msg-row { display: flex; margin: 10px 0; }
        .msg-row-user { justify-content: flex-end; }
        .msg-row-assistant { justify-content: flex-start; }
        .bubble {
            max-width: 82%; padding: 10px 14px; border-radius: 14px;
            line-height: 1.65; font-size: 0.95rem; overflow-wrap: anywhere;
        }
        .bubble-user { background: #2f7bf6; color: #ffffff; border-bottom-right-radius: 4px; }
        .bubble-assistant { background: #f2f3f5; color: #1f2328; border-bottom-left-radius: 4px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<h2 class="chat-title">AdaptFin</h2>', unsafe_allow_html=True)
    st.markdown('<div class="chat-sub">多Agent协同的智能投资顾问</div>', unsafe_allow_html=True)

    with st.expander("📋 风险测评（10 题，保存后覆盖当前画像并留历史）", expanded=False):
        with st.form("risk_form"):
            answers = {}
            for q in QUESTIONNAIRE:
                labels = [o.text for o in q.options]
                picked = st.radio(q.text, labels, key=f"q_{q.id}")
                answers[q.id] = next(o.score for o in q.options if o.text == picked)
            if st.form_submit_button("保存测评结果"):
                risk = score_answers(answers)
                store.set_risk(user_id, risk)
                st.success(f"已保存：{risk.level.value}（{risk.score}/60），历史记录保留可查。")
                st.rerun()

    history_key = f"history_{user_id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    for role, content in st.session_state[history_key]:
        st.markdown(_bubble(role, content), unsafe_allow_html=True)

    pending_key = f"pending_{user_id}"
    if st.session_state.get(pending_key):
        # 先展示“正在思考…”，再执行模型调用；完成后清占位并重绘
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            _bubble("assistant", "正在思考…"),
            unsafe_allow_html=True,
        )
        try:
            result = _ask(graph, user_id, thread, st.session_state[history_key][-1][1])
            answer = result.get("final_answer") or "（无回答）"
        except Exception as exc:
            answer = f"本轮调用失败：{exc}"
        finally:
            thinking_placeholder.empty()
        st.session_state[pending_key] = False
        st.session_state[history_key].append(("assistant", answer))
        st.rerun()

    prompt = st.chat_input("试试：600519 现在多少钱 / 分析我的持仓 / 我想做风险测评")
    if prompt:
        st.session_state[history_key].append(("user", prompt))
        st.session_state[pending_key] = True
        st.rerun()  # 先重绘：立刻显示用户消息 + 思考占位


if __name__ == "__main__":
    main()
