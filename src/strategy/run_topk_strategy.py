"""
V1.0 TopK strategy CLI.

Usage::

    python -m src.strategy.run_topk_strategy --strategy single_return_20d_top20 --limit 5
    python -m src.strategy.run_topk_strategy --factor-name return_20d --top-k 20 --limit 5
    python -m src.strategy.run_topk_strategy --factor-weights '{"return_20d":0.5,"momentum_20d":0.5}' --top-k 20 --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys

from config.logging_config import setup_logging
from src.strategy.selector import run_and_save_strategy
from src.strategy.strategy_config import get_default_strategy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V1.0 TopK Stock Selection Strategy")
    parser.add_argument("--strategy", default=None, help="Default strategy name")
    parser.add_argument("--factor-name", default=None)
    parser.add_argument("--factor-weights", default=None, help='JSON weights, e.g. {"return_20d":0.5,"momentum_20d":0.5}')
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--trade-date", default=None, help="YYYYMMDD")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    setup_logging()

    # Build config
    is_adhoc = False
    if args.strategy:
        config = get_default_strategy(args.strategy)
        if config is None:
            print(f"[ERROR] Unknown default strategy: {args.strategy}")
            return 1
    elif args.factor_name:
        is_adhoc = True
        config = {
            "strategy_name": f"adhoc_{args.factor_name}_top{args.top_k}",
            "strategy_type": "single_factor",
            "factor_name": args.factor_name,
            "top_k": args.top_k,
            "is_active": True,
        }
    elif args.factor_weights:
        is_adhoc = True
        try:
            weights = json.loads(args.factor_weights)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON for --factor-weights: {e}")
            return 1
        config = {
            "strategy_name": "adhoc_multi_top{}".format(args.top_k),
            "strategy_type": "multi_factor",
            "factor_weights": weights,
            "top_k": args.top_k,
            "is_active": True,
        }
    else:
        print("[ERROR] Please provide --strategy, --factor-name, or --factor-weights")
        return 1

    print(f"Strategy     : {config['strategy_name']}")
    print(f"Type         : {config['strategy_type']}")
    print(f"Top-K        : {config.get('top_k', 20)}")
    if args.trade_date: print(f"Trade date   : {args.trade_date}")
    if args.start_date: print(f"Start date   : {args.start_date}")
    if args.end_date: print(f"End date     : {args.end_date}")
    if args.limit: print(f"Limit        : {args.limit}")
    print()

    result = run_and_save_strategy(
        config, trade_date=args.trade_date,
        start_date=args.start_date, end_date=args.end_date,
        limit=args.limit, save_config=not is_adhoc,
    )

    print("--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
