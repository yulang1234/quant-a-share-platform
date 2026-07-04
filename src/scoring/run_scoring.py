"""V1.3 multi-factor scoring CLI."""
from __future__ import annotations
import argparse, sys
from config.logging_config import setup_logging
from src.scoring.score_calculator import run_scoring


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="V1.3 Multi-Factor Scoring System")
    p.add_argument("--model", required=True, help="Model name (momentum_quality_score, trend_volume_score, low_vol_stable_score)")
    p.add_argument("--trade-date", default=None, help="YYYYMMDD")
    p.add_argument("--start-date", default=None, help="YYYYMMDD")
    p.add_argument("--end-date", default=None, help="YYYYMMDD")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args(argv)
    setup_logging()

    print(f"Model       : {args.model}")
    if args.trade_date: print(f"Trade date  : {args.trade_date}")
    if args.start_date: print(f"Start date  : {args.start_date}")
    if args.end_date: print(f"End date    : {args.end_date}")
    if args.limit: print(f"Limit       : {args.limit}")
    print()

    r = run_scoring(args.model, args.trade_date, args.start_date, args.end_date, args.limit)
    print("--- Result ---")
    for k, v in r.items(): print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__": sys.exit(main())
