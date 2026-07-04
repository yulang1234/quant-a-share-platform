"""
V0.8 factor ranking CLI.

Usage::

    python -m src.factor_rank.run_factor_ranking --pool core_500 --limit 5
    python -m src.factor_rank.run_factor_ranking --factor-name return_20d --limit 5
"""

from __future__ import annotations

import argparse
import logging
import sys

from config.logging_config import setup_logging
from src.factor_rank.rank_calculator import run_factor_ranking

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V0.8 Factor Standardization & Ranking")
    parser.add_argument("--pool", default="core_500", help="Pool name")
    parser.add_argument("--factor-name", default=None, help="Single factor name")
    parser.add_argument("--trade-date", default=None, help="YYYYMMDD")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--limit", type=int, default=None, help="Max rows")
    args = parser.parse_args(argv)

    setup_logging()

    print(f"Pool        : {args.pool}")
    if args.factor_name:
        print(f"Factor      : {args.factor_name}")
    if args.trade_date:
        print(f"Trade date  : {args.trade_date}")
    if args.start_date:
        print(f"Start date  : {args.start_date}")
    if args.end_date:
        print(f"End date    : {args.end_date}")
    if args.limit:
        print(f"Limit       : {args.limit}")
    print()

    result = run_factor_ranking(
        pool_name=args.pool,
        factor_name=args.factor_name,
        trade_date=args.trade_date,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )

    print("--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
