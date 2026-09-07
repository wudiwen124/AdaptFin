from advisor.evaluation.cases import GOLDEN_CASES
from advisor.evaluation.runner import (
    export_cases,
    run_architectures,
    run_benchmark,
    write_report,
)
from advisor.llm.fake_gateway import FakeGateway


def test_supervisor_golden_routing(tmp_path):
    cases = GOLDEN_CASES[:5]  # 覆盖 quote/research/portfolio/risk/chat
    results, summary = run_benchmark(
        architecture="supervisor",
        gateway=FakeGateway(),
        store_dir=tmp_path / "eval",
        cases=cases,
    )
    assert summary["cases"] == 5
    assert summary["intent_pass"] == 5
    assert summary["completion_pass"] == 5
    assert summary["disclaimer_pass"] >= 4  # chat 用例不要求免责，故计为通过
    assert all(r["audit_issue"] is None for r in results)


def test_architectures_report(tmp_path):
    cases = GOLDEN_CASES[:3]
    results_by_arch, summaries = run_architectures(
        gateway=FakeGateway(),
        cases=cases,
        store_dir=tmp_path / "arch",
    )
    assert set(results_by_arch) == {"single", "fixed", "supervisor"}
    assert len(summaries) == 3

    report = write_report(tmp_path / "report.md", summaries)
    text = report.read_text(encoding="utf-8")
    assert "三架构对照实验报告" in text
    assert "supervisor" in text and "single" in text and "fixed" in text


def test_export_cases(tmp_path):
    path = tmp_path / "golden_cases.jsonl"
    export_cases(path)
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == len(GOLDEN_CASES)
