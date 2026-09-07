"""评测执行器：跑用例、算指标、出报告。"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

from advisor.config import Settings
from advisor.datasources import DataSourceRouter, build_default_router
from advisor.evaluation.cases import GOLDEN_CASES, GoldenCase, make_profile
from advisor.graph.builder import build_app
from advisor.llm.client import ModelGateway
from advisor.llm.fake_gateway import FakeGateway
from advisor.store import ProfileStore


class CountingGateway:
    """给任意网关计 LLM 调用次数（评测指标用）。"""

    def __init__(self, inner: ModelGateway | FakeGateway) -> None:
        self.inner = inner
        self.calls = 0

    def chat(self, messages, **kwargs) -> dict:
        self.calls += 1
        return self.inner.chat(messages, **kwargs)


def _extract_codes(text: str) -> list[str]:
    return re.findall(r"(?<!\d)(\d{6})(?!\d)", text)


def analyze_case(state: dict, case: GoldenCase, gateway: CountingGateway) -> dict:
    final = state.get("final_answer") or ""
    return {
        "case_id": case.id,
        "category": case.category,
        "intent": state.get("intent"),
        "intent_ok": (case.expected_intent is None) or (state.get("intent") == case.expected_intent),
        "completion_ok": bool(final.strip()),
        "disclaimer_ok": _disclaimer_ok(case, final),
        "contains_ok": all(token in final for token in case.expected_contains),
        "llm_calls": gateway.calls,
        "tool_calls": len(state.get("tool_observations") or []),
        "audit_issue": state.get("audit_issue"),
    }


def _disclaimer_ok(case: GoldenCase, final: str) -> bool:
    """仅当用例显式要求免责声明时才计分。"""
    if "不构成投资建议" in case.expected_contains:
        return "不构成投资建议" in final
    return True


def _seed_store(store: ProfileStore, case: GoldenCase, user_id: str) -> None:
    if case.seed_risk_level is not None:
        store.set_risk(user_id, make_profile(case.seed_risk_level))


def run_benchmark(
    *,
    architecture: str = "supervisor",
    gateway: ModelGateway | FakeGateway | None = None,
    settings: Settings | None = None,
    store_dir: Path | None = None,
    cases: list[GoldenCase] | None = None,
) -> tuple[list[dict], dict]:
    """用同一 LLM 网关跑指定架构的全部用例，返回 (逐条结果, 汇总)。"""
    gateway = gateway or FakeGateway()
    cases = cases or GOLDEN_CASES
    store_dir = store_dir or Path("data/eval_tmp")
    store_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]  # 每次运行唯一，避免共享 checkpoint 串轮

    results: list[dict] = []
    for idx, case in enumerate(cases):
        counting = CountingGateway(gateway)
        store = ProfileStore(store_dir / f"case_{idx}.db")
        user_id = f"eval_{case.id}"
        _seed_store(store, case, user_id)
        router = build_default_router(settings or _demo_settings())
        app = build_app(gateway=counting, router=router, store=store, settings=_demo_settings())
        out = app.invoke(
            {"user_id": user_id, "messages": [HumanMessage(content=case.message)]},
            config={"configurable": {"thread_id": f"eval_{architecture}_{case.id}_{run_id}"}},
        )
        results.append(analyze_case(out, case, counting))

    total = len(results)
    summary = {
        "architecture": architecture,
        "cases": total,
        "intent_pass": sum(1 for r in results if r["intent_ok"]),
        "completion_pass": sum(1 for r in results if r["completion_ok"]),
        "disclaimer_pass": sum(1 for r in results if r["disclaimer_ok"]),
        "contains_pass": sum(1 for r in results if r["contains_ok"]),
        "avg_llm_calls": round(sum(r["llm_calls"] for r in results) / max(total, 1), 2),
        "avg_tool_calls": round(sum(r["tool_calls"] for r in results) / max(total, 1), 2),
    }
    return results, summary


def _demo_settings() -> Settings:
    from advisor.config import DataConfig

    return Settings(data=DataConfig(sources_priority=["demo"]))


def write_report(path: Path, summaries: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 三架构对照实验报告",
        "",
        "> 评测与收益分离：指标只衡量路由/完成/合规/成本，不衡量涨跌。",
        "",
        "> 说明：single/fixed 无路由概念，intent 列固定计通过；“工具调用”需真实 LLM 才会触发，离线 fake 网关下为 0。",
        "",
        "| 架构 | 用例数 | 意图通过 | 完成通过 | 免责通过 | 内容通过 | 平均LLM调用 | 平均工具调用 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['architecture']} | {s['cases']} | {s['intent_pass']} | {s['completion_pass']} | "
            f"{s['disclaimer_pass']} | {s['contains_pass']} | {s['avg_llm_calls']} | {s['avg_tool_calls']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_details(path: Path, results: list[dict]) -> Path:
    """逐用例明细（JSONL）：定位“内容命中失败”的具体 case。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return path


def export_cases(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for case in GOLDEN_CASES:
            f.write(
                json.dumps(
                    {
                        "id": case.id,
                        "category": case.category,
                        "message": case.message,
                        "expected_intent": case.expected_intent,
                        "expected_contains": case.expected_contains,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def run_architectures(
    *,
    gateway=None,
    cases: list[GoldenCase] | None = None,
    architectures: list[str] | None = None,
    store_dir: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """跑全部架构并汇总（single / fixed / supervisor）。"""
    gateway = gateway or FakeGateway()
    archs = architectures or ["single", "fixed", "supervisor"]
    results_by_arch: dict[str, list[dict]] = {}
    summaries: list[dict] = []
    for arch in archs:
        if arch == "supervisor":
            results, summary = run_benchmark(architecture=arch, gateway=gateway, cases=cases, store_dir=store_dir)
        elif arch == "single":
            results, summary = _run_single(gateway, cases, store_dir)
        elif arch == "fixed":
            results, summary = _run_fixed(gateway, cases, store_dir)
        else:
            raise ValueError(f"未知架构: {arch}")
        results_by_arch[arch] = results
        summaries.append(summary)
    return results_by_arch, summaries


def _run_single(gateway, cases, store_dir) -> tuple[list[dict], list[dict]]:
    """单 Agent + 全工具：无路由、无审计的对照组。"""
    cases = cases or GOLDEN_CASES
    store_dir = store_dir or Path("data/eval_tmp")
    store_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    results = []
    for idx, case in enumerate(cases):
        counting = CountingGateway(gateway)
        store = ProfileStore(store_dir / f"single_{idx}.db")
        user_id = f"eval_{case.id}"
        _seed_store(store, case, user_id)
        router = build_default_router(_demo_settings())
        tools = _all_tools(router)
        app = _single_graph(counting, router)
        out = app.invoke(
            {"user_id": user_id, "messages": [HumanMessage(content=case.message)]},
            config={"configurable": {"thread_id": f"single_{case.id}_{run_id}"}},
        )
        results.append(
            {
                "case_id": case.id,
                "category": case.category,
                "intent": None,
                "intent_ok": True,  # 单 Agent 无路由概念，不扣分
                "completion_ok": bool((out.get("final_answer") or "").strip()),
                "disclaimer_ok": _disclaimer_ok(case, out.get("final_answer") or ""),
                "contains_ok": all(t in (out.get("final_answer") or "") for t in case.expected_contains),
                "llm_calls": counting.calls,
                "tool_calls": len(out.get("tool_observations") or []),
                "audit_issue": None,
            }
        )
    summary = _summarize("single", results)
    return results, summary


def _run_fixed(gateway, cases, store_dir) -> tuple[list[dict], list[dict]]:
    """固定流水线：有代码就跑三分析师 + Advisor + Auditor，无动态路由。"""
    cases = cases or GOLDEN_CASES
    store_dir = store_dir or Path("data/eval_tmp")
    store_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    results = []
    for idx, case in enumerate(cases):
        counting = CountingGateway(gateway)
        store = ProfileStore(store_dir / f"fixed_{idx}.db")
        user_id = f"eval_{case.id}"
        _seed_store(store, case, user_id)
        router = build_default_router(_demo_settings())
        app = _fixed_graph(counting, router)
        out = app.invoke(
            {"user_id": user_id, "messages": [HumanMessage(content=case.message)]},
            config={"configurable": {"thread_id": f"fixed_{case.id}_{run_id}"}},
        )
        results.append(
            {
                "case_id": case.id,
                "category": case.category,
                "intent": None,
                "intent_ok": True,  # 固定流水线无意图分派，路由指标不计
                "completion_ok": bool((out.get("final_answer") or "").strip()),
                "disclaimer_ok": _disclaimer_ok(case, out.get("final_answer") or ""),
                "contains_ok": all(t in (out.get("final_answer") or "") for t in case.expected_contains),
                "llm_calls": counting.calls,
                "tool_calls": len(out.get("tool_observations") or []),
                "audit_issue": out.get("audit_issue"),
            }
        )
    summary = _summarize("fixed", results)
    return results, summary


def _summarize(architecture: str, results: list[dict]) -> dict:
    total = len(results)
    return {
        "architecture": architecture,
        "cases": total,
        "intent_pass": sum(1 for r in results if r["intent_ok"]),
        "completion_pass": sum(1 for r in results if r["completion_ok"]),
        "disclaimer_pass": sum(1 for r in results if r["disclaimer_ok"]),
        "contains_pass": sum(1 for r in results if r["contains_ok"]),
        "avg_llm_calls": round(sum(r["llm_calls"] for r in results) / max(total, 1), 2),
        "avg_tool_calls": round(sum(r["tool_calls"] for r in results) / max(total, 1), 2),
    }


def _all_tools(router):
    from advisor.tools.market_tools import build_market_tools

    return build_market_tools(router)


def _single_graph(gateway, router):
    from functools import partial

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    from advisor.graph.nodes.agent import run_tool_agent

    class SingleState(TypedDict):
        user_id: str
        messages: Annotated[list[Any], add_messages]
        final_answer: str | None

    tools = _all_tools(router)

    def node(state: SingleState) -> dict:
        user_text = ""
        for msg in reversed(state.get("messages") or []):
            content = msg.content if hasattr(msg, "content") else None
            role = getattr(msg, "type", "")
            if role == "human" and content:
                user_text = str(content)
                break
        run = run_tool_agent(
            gateway,
            system_prompt="你是全能投顾助手。用全部工具回答问题，直接给最终结论。",
            user_text=user_text,
            tools=tools,
            tier="deep",
        )
        return {"final_answer": run.text}

    g = StateGraph(SingleState)
    g.add_node("agent", node)
    g.add_edge(START, "agent")
    g.add_edge("agent", END)
    return g.compile(checkpointer=MemorySaver())


def _fixed_graph(gateway, router):
    from functools import partial

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    from advisor.graph.nodes.advisor import advisor_node
    from advisor.graph.nodes.auditor import auditor_node
    from advisor.graph.nodes.research import research_one_node

    class FixedState(TypedDict):
        user_id: str
        messages: Annotated[list[Any], add_messages]
        research_results: list[Any]
        tool_observations: list[Any]
        sources: list[str]
        final_answer: str | None
        audit_round: int
        audit_issue: str | None

    tools = _all_tools(router)

    def node(state: FixedState) -> dict:
        user_text = ""
        for msg in reversed(state.get("messages") or []):
            content = msg.content if hasattr(msg, "content") else None
            role = getattr(msg, "type", "")
            if role == "human" and content:
                user_text = str(content)
                break
        codes = _extract_codes(user_text)
        reports, observations = [], []
        for code in codes:
            res = research_one_node(
                {"symbol": code, "user_text": user_text},
                gateway=gateway,
                tools=tools,
            )
            reports.extend(res["research_results"])
            observations.extend(res["tool_observations"])
        if not codes:
            from advisor.graph.nodes.agent import run_tool_agent

            run = run_tool_agent(
                gateway,
                system_prompt="你是全能投顾助手，用工具或常识回答。",
                user_text=user_text,
                tools=tools,
            )
            return {"final_answer": run.text}
        merged = {
            **state,
            "research_results": reports,
            "tool_observations": observations,
            "risk_profile": None,
            "agent_context": None,
        }
        advised = advisor_node(merged, gateway=gateway)
        merged["final_answer"] = advised["final_answer"]
        audited = auditor_node(merged)
        return {
            "research_results": reports,
            "tool_observations": observations,
            "sources": [],
            "final_answer": audited["final_answer"],
            "audit_round": audited.get("audit_round", 0),
            "audit_issue": audited.get("audit_issue"),
        }

    g = StateGraph(FixedState)
    g.add_node("fixed", node)
    g.add_edge(START, "fixed")
    g.add_edge("fixed", END)
    return g.compile(checkpointer=MemorySaver())
