"""三架构对照实验 CLI。

用法：
    python scripts/run_benchmark.py --arch all          # fake 网关（离线）
    python scripts/run_benchmark.py --arch supervisor   # 只跑 Supervisor
"""

from __future__ import annotations

import argparse
from pathlib import Path

from advisor.evaluation.cases import GOLDEN_CASES
from advisor.evaluation.runner import run_architectures, write_details, write_report
from advisor.llm.client import build_gateway


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default="all", choices=["single", "fixed", "supervisor", "all"])
    parser.add_argument("--limit", type=int, default=0, help="限制用例数（0=全部）")
    parser.add_argument("--out", type=Path, default=Path("results/benchmark_report.md"))
    parser.add_argument("--real", action="store_true", help="用 .env 里的真实 LLM 跑（默认离线 fake）")
    parser.add_argument("--details", type=Path, default=None, help="逐用例明细输出路径（JSONL）")
    parser.add_argument("--case", default=None, help="只跑指定 case_id")
    args = parser.parse_args()

    cases = GOLDEN_CASES[: args.limit] if args.limit else GOLDEN_CASES
    if args.case:
        cases = [c for c in cases if c.id == args.case]
    archs = ["single", "fixed", "supervisor"] if args.arch == "all" else [args.arch]
    gateway = build_gateway() if args.real else None
    results_by_arch, summaries = run_architectures(architectures=archs, cases=cases, gateway=gateway)
    report = write_report(args.out, summaries)
    print(f"报告已写入: {report}")
    if args.details:
        for arch_name, arch_results in results_by_arch.items():
            details_path = args.details if len(archs) == 1 else args.details.with_name(f"{args.details.stem}_{arch_name}.jsonl")
            write_details(details_path, arch_results)
            print(f"明细已写入: {details_path}")
    for s in summaries:
        print(
            f"{s['architecture']:>10} | cases={s['cases']} | intent={s['intent_pass']} "
            f"| disclaimer={s['disclaimer_pass']} | avg_llm={s['avg_llm_calls']} | avg_tool={s['avg_tool_calls']}"
        )


if __name__ == "__main__":
    main()
