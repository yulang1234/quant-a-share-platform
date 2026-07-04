"""
V0.7 factor calculation CLI.

Usage::

    python -m src.factors.run_factor_calculation --pool core_500 --limit 5
    python -m src.factors.run_factor_calculation --stock-code 000001
    python -m src.factors.run_factor_calculation --stock-code 000001 --start-date 20200101 --end-date 20231231
"""

from __future__ import annotations

import argparse
import logging
import sys

from config.logging_config import setup_logging
from src.factors.factor_calculator import run_factor_calculation

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V0.7 Basic Factor Calculation")
    parser.add_argument("--pool", default="core_500", help="Pool name")
    parser.add_argument("--stock-code", default=None, help="6-digit stock code")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--limit", type=int, default=None, help="Max stocks")
    args = parser.parse_args(argv)

    setup_logging()

    stock_code = None
    if args.stock_code:
        stock_code = str(args.stock_code).strip().zfill(6)
        if len(stock_code) != 6 or not stock_code.isdigit():
            print(f"[ERROR] --stock-code must be 6 digits, got '{args.stock_code}'")
            return 1

    print(f"Pool       : {args.pool}")
    if stock_code:
        print(f"Stock      : {stock_code}")
    if args.start_date:
        print(f"Start date : {args.start_date}")
    if args.end_date:
        print(f"End date   : {args.end_date}")
    if args.limit:
        print(f"Limit      : {args.limit}")
    print()

    result = run_factor_calculation(
        pool_name=args.pool,
        stock_code=stock_code,
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
