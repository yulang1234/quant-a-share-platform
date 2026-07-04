"""
V0.9 factor effectiveness analysis — CLI + run pipeline.

Usage::

    python -m src.factor_analysis.run_factor_analysis --pool core_500 --limit 5
    python -m src.factor_analysis.run_factor_analysis --factor-name return_20d --forward-days 5 --limit 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from config.logging_config import setup_logging
from src.factor_analysis.analysis_summary import save_analysis_summary, summarize_factor_analysis
from src.factor_analysis.forward_returns import (
    calculate_forward_returns,
    get_price_data_for_forward_returns,
    save_forward_returns,
)
from src.factor_analysis.group_analysis import calculate_group_returns, save_group_return_report
from src.factor_analysis.ic_analysis import calculate_daily_ic, save_ic_report
from src.storage.duckdb_repo import fetch_factor_rankings, query_df
from src.universe.stock_pool import get_active_stock_pool

logger = logging.getLogger(__name__)


def run_factor_analysis(
    pool_name: str = "core_500",
    factor_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    forward_days: int = 5,
    group_count: int = 5,
    limit: int | None = None,
) -> dict[str, Any]:
    """Full V0.9 pipeline."""

    # 1. Forward returns from qfq
    pool = get_active_stock_pool()
    stock_codes = pool["stock_code"].astype(str).str.zfill(6).tolist()
    if limit:
        stock_codes = stock_codes[:limit]

    price_df = get_price_data_for_forward_returns(
        stock_codes=stock_codes, start_date=start_date, end_date=end_date,
        forward_days=forward_days, limit=limit,
    )
    if price_df.empty:
        return {"factor_count": 0, "forward_return_rows": 0, "ic_rows": 0, "group_rows": 0, "summary_rows": 0, "status": "skipped (no price data)"}

    fwd_df = calculate_forward_returns(price_df, forward_days)
    fwd_rows = save_forward_returns(fwd_df)

    if fwd_df.empty:
        return {"factor_count": 0, "forward_return_rows": fwd_rows, "ic_rows": 0, "group_rows": 0, "summary_rows": 0, "status": "skipped (no forward returns)"}

    # 2. Get factor names
    if factor_name:
        factor_names = [factor_name]
    else:
        rank_sample = fetch_factor_rankings(limit=1)
        if rank_sample.empty:
            return {"factor_count": 0, "forward_return_rows": fwd_rows, "ic_rows": 0, "group_rows": 0, "summary_rows": 0, "status": "skipped (no rank data)"}
        # Get available factor names from stock_factor_rank
        all_names = query_df("SELECT DISTINCT factor_name FROM stock_factor_rank").values.flatten().tolist()
        factor_names = [str(f) for f in all_names]

    if not factor_names:
        return {"factor_count": 0, "forward_return_rows": fwd_rows, "ic_rows": 0, "group_rows": 0, "summary_rows": 0, "status": "skipped (no factors)"}

    # 3. For each factor: IC + group returns + summary
    ic_total = 0
    group_total = 0
    summary_total = 0

    for fn in factor_names:
        rank_df = fetch_factor_rankings(factor_name=fn, start_date=start_date, end_date=end_date)
        if rank_df.empty:
            continue

        # IC
        ic = calculate_daily_ic(rank_df, fwd_df, fn, forward_days)
        ic_total += save_ic_report(ic)

        # Group returns
        grp = calculate_group_returns(rank_df, fwd_df, fn, forward_days, group_count)
        group_total += save_group_return_report(grp)

        # Summary
        summary = summarize_factor_analysis(ic, grp, fn, forward_days, start_date, end_date)
        summary_total += save_analysis_summary(summary)

    return {
        "factor_count": len(factor_names),
        "forward_return_rows": fwd_rows,
        "ic_rows": ic_total,
        "group_rows": group_total,
        "summary_rows": summary_total,
        "status": "success",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V0.9 Factor Effectiveness Analysis")
    parser.add_argument("--pool", default="core_500")
    parser.add_argument("--factor-name", default=None)
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--group-count", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    setup_logging()

    print(f"Pool         : {args.pool}")
    if args.factor_name:
        print(f"Factor       : {args.factor_name}")
    print(f"Forward days : {args.forward_days}")
    if args.start_date:
        print(f"Start date   : {args.start_date}")
    if args.end_date:
        print(f"End date     : {args.end_date}")
    if args.limit:
        print(f"Limit        : {args.limit}")
    print()

    result = run_factor_analysis(
        pool_name=args.pool, factor_name=args.factor_name,
        start_date=args.start_date, end_date=args.end_date,
        forward_days=args.forward_days, group_count=args.group_count,
        limit=args.limit,
    )

    print("--- Result ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
