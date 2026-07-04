"""
V1.1 backtest CLI.

Usage::

    python -m src.backtest.run_backtest --strategy single_return_20d_top20 --limit 5
    python -m src.backtest.run_backtest --strategy multi_momentum_quality_top20 --top-k 20 --rebalance-frequency monthly --limit 5
"""

from __future__ import annotations

import argparse
import sys

from config.logging_config import setup_logging
from src.backtest.backtest_engine import run_basic_backtest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V1.1 Basic Backtest Engine")
    parser.add_argument("--strategy", default=None, help="Strategy name (required)")
    parser.add_argument("--backtest-name", default=None)
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--rebalance-frequency", default="monthly", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    setup_logging()

    if not args.strategy:
        print("[ERROR] --strategy is required")
        return 1

    print(f"Strategy           : {args.strategy}")
    print(f"Initial cash       : {args.initial_cash:,.0f}")
    print(f"Top-K              : {args.top_k}")
    print(f"Rebalance frequency: {args.rebalance_frequency}")
    if args.start_date: print(f"Start date         : {args.start_date}")
    if args.end_date: print(f"End date           : {args.end_date}")
    if args.limit: print(f"Limit              : {args.limit}")
    print()

    result = run_basic_backtest(
        backtest_name=args.backtest_name,
        strategy_name=args.strategy,
        start_date=args.start_date, end_date=args.end_date,
        initial_cash=args.initial_cash, top_k=args.top_k,
        rebalance_frequency=args.rebalance_frequency, limit=args.limit,
    )

    print("--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
