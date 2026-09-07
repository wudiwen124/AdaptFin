"""P16 UI 端到端功能冒烟：用主图离线跑通 UI 清单里的核心链路。

浏览器视觉手测仍需按 docs/UI_E2E清单.md 执行；本脚本保证背后逻辑全通。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage

from advisor.config import DataConfig, Settings, StoreConfig
from advisor.datasources import build_default_router
from advisor.graph.builder import build_app
from advisor.llm.fake_gateway import FakeGateway
from advisor.store import ProfileStore


def main() -> int:
    tmp = Path("data/e2e_smoke")
    tmp.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        data=DataConfig(sources_priority=["demo"]),
        store=StoreConfig(db_path=str(tmp / "p.db"), checkpoint_db_path=str(tmp / "ck.db")),
    )
    store = ProfileStore(settings.store.db_path)
    app = build_app(
        gateway=FakeGateway(),
        router=build_default_router(settings),
        store=store,
        settings=settings,
    )
    user, thread = "ui_smoke", "ui_smoke"

    def ask(text: str) -> dict:
        return app.invoke(
            {"user_id": user, "messages": [HumanMessage(content=text)]},
            config={"configurable": {"thread_id": thread}},
        )

    checks: list[tuple[str, bool, str]] = []

    first = ask("我想做风险测评")
    checks.append(("测评开始", first["q_index"] == 1 and "1/10" in (first["final_answer"] or ""), "问卷首题"))
    for _ in range(10):
        ask("1")
    checks.append(("测评完成 C1", store.get_profile(user).risk.level.value == "C1", "画像落库"))

    ask("我买了100股510300，偏好红利低波")
    checks.append(("持仓与偏好入库", [h.symbol for h in store.get_holdings(user)] == ["510300"], "holdings"))

    research = ask("贵州茅台现在怎么样")
    checks.append(("名称触发研究", research["intent"] == "research" and research["symbols"] == ["600519"], "research"))

    quote = ask("它现在多少钱")
    checks.append(
        ("指代消解后真取数", quote["intent"] == "quote" and quote["symbols"] == ["600519"] and quote["tool_observations"], "pronoun")
    )

    recall = ask("低波动高分红的方向我提过吗")
    checks.append(("换说法记忆召回", "红利低波" in (recall.get("user_memory") or ""), "recall"))

    ok = True
    for name, passed, note in checks:
        print(("PASS" if passed else "FAIL"), name, "-", note)
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
