"""P4-1 评测：黄金用例 + 三架构对照实验。

评测与收益分离：这里只回答“Agent 工程是否可靠”，不回答“能不能赚钱”。
"""

from advisor.evaluation.cases import GOLDEN_CASES, GoldenCase
from advisor.evaluation.runner import analyze_case, run_benchmark

__all__ = ["GOLDEN_CASES", "GoldenCase", "analyze_case", "run_benchmark"]
