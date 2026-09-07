"""离线演示：用 demo 数据源跑通 行情 → 指标 全链路。

用法:  python scripts/demo_cli.py 600519
"""

from __future__ import annotations

import argparse
import json

from advisor.config import DataConfig, Settings
from advisor.datasources import build_default_router
from advisor.schemas.common import Symbol
from advisor.tools.indicators import compute_trend_indicators


def main() -> None:
    parser = argparse.ArgumentParser(description="demo 数据链路冒烟测试")
    parser.add_argument("symbol", default="600519", nargs="?")
    args = parser.parse_args()

    settings = Settings(data=DataConfig(sources_priority=["demo"]))
    router = build_default_router(settings)
    symbol = Symbol.parse(args.symbol)

    quote = router.realtime_quote(symbol)
    print("== 实时行情 ==")
    print(json.dumps(quote.model_dump(mode="json"), ensure_ascii=False, indent=2))

    kline = router.kline(symbol, days=120)
    print("\n== 技术指标 ==")
    print(json.dumps(compute_trend_indicators(kline).model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
