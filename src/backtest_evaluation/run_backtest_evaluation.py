"""V1.2 backtest evaluation CLI."""
from __future__ import annotations
import argparse, sys
from config.logging_config import setup_logging
from src.backtest_evaluation.evaluation_engine import run_backtest_evaluation


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="V1.2 Backtest Evaluation")
    p.add_argument("--backtest-name", required=True)
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date", default=None)
    p.add_argument("--risk-free-rate", type=float, default=0.0)
    args = p.parse_args(argv)
    setup_logging()

    print(f"Backtest         : {args.backtest_name}")
    if args.start_date: print(f"Start date       : {args.start_date}")
    if args.end_date: print(f"End date         : {args.end_date}")
    print(f"Risk-free rate   : {args.risk_free_rate}")
    print()

    r = run_backtest_evaluation(args.backtest_name, args.start_date, args.end_date, args.risk_free_rate)
    print("--- Result ---")
    for k, v in r.items(): print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__": sys.exit(main())
