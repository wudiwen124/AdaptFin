"""P2 对话 CLI：真实调用 LangGraph 主图。

用法：
    python scripts/chat_cli.py                          # 交互模式
    python scripts/chat_cli.py --ask-file 问题.txt       # 单轮模式

默认从 .env 读取 LLM key / 模型 / 数据源优先级；会话线程见 --thread。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from langchain_core.messages import HumanMessage

from advisor.graph.builder import build_app


def _invoke(app, user_id: str, thread: str, text: str) -> dict:
    return app.invoke(
        {"user_id": user_id, "messages": [HumanMessage(content=text)]},
        config={"configurable": {"thread_id": thread}},
    )


def _print_result(result: dict) -> None:
    print("\n[Assistant]")
    print(result.get("final_answer") or "（无回答）")
    if result.get("sources"):
        print("\n[工具轨迹]", " | ".join(result["sources"][-8:]))


def _invoke_safe(app, user_id: str, thread: str, text: str) -> dict | None:
    try:
        return _invoke(app, user_id, thread, text)
    except Exception as exc:
        print(f"\n[本轮调用失败] {exc}\n请稍后重试或换个说法。")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="多 Agent 投顾助手 CLI（P2）")
    parser.add_argument("--user", default="demo_user")
    parser.add_argument("--thread", default=None, help="默认按用户隔离")
    parser.add_argument("--ask-file", type=Path, default=None, help="单轮模式：从 UTF-8 文件读取问题")
    args = parser.parse_args()

    app = build_app()
    thread = args.thread or f"cli_{args.user}"

    if args.ask_file:
        text = args.ask_file.read_text(encoding="utf-8").strip()
        result = _invoke_safe(app, args.user, thread, text)
        if result:
            _print_result(result)
        return

    print("多 Agent 智能投顾助手（P2 CLI）输入问题开始；输入 exit 退出。")
    while True:
        try:
            text = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"exit", "quit", "退出"}:
            break
        if text:
            result = _invoke_safe(app, args.user, thread, text)
            if result:
                _print_result(result)


if __name__ == "__main__":
    main()
