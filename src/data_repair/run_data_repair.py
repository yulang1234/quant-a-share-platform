"""
V0.6 data-repair CLI entry point.

Usage::

    python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action plan --dry-run
    python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj raw --action refetch --start-date 20260701 --end-date 20260703 --no-dry-run --confirm
"""

from __future__ import annotations

import argparse
import logging
import sys

from config.logging_config import setup_logging

logger = logging.getLogger(__name__)

VALID_ACTIONS = frozenset({"plan", "deduplicate", "refetch", "rebuild-parquet", "auto"})
VALID_ADJ = frozenset({"raw", "qfq", "all"})


def main(argv: list[str] | None = None) -> int:
    """Run data repair from command-line arguments."""
    parser = argparse.ArgumentParser(
        description="V0.6 Data Repair & Re-fetch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pool", default="core_500", help="Pool name")
    parser.add_argument("--stock-code", default=None, help="6-digit stock code")
    parser.add_argument("--issue-type", default="all",
                        help="duplicate/price_anomaly/missing_trade_date/all")
    parser.add_argument("--adj", default="all", choices=sorted(VALID_ADJ))
    parser.add_argument("--limit", type=int, default=None, help="Max rows/stocks")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD")
    parser.add_argument("--action", default="plan", choices=sorted(VALID_ACTIONS))
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview only (default)")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                        help="Execute real changes (requires --confirm)")
    parser.add_argument("--confirm", action="store_true", default=False,
                        help="Allow real data modification")
    parser.add_argument("--recheck", action="store_true", default=False,
                        help="Re-run quality check after repair")

    args = parser.parse_args(argv)
    setup_logging()

    # Ensure DB schema is up-to-date (creates data_repair_log if missing)
    try:
        from src.storage.duckdb_repo import init_database
        init_database()
    except Exception as exc:
        print(f"[ERROR] Cannot open database: {exc}")
        return 1

    # Safety: confirm required for real execution
    if not args.dry_run and not args.confirm:
        print("[ERROR] --no-dry-run requires --confirm to execute real changes.")
        return 1

    # Validate stock-code
    stock_code = None
    if args.stock_code:
        stock_code = str(args.stock_code).strip().zfill(6)
        if len(stock_code) != 6 or not stock_code.isdigit():
            print(f"[ERROR] --stock-code must be 6 digits, got '{args.stock_code}'")
            return 1

    dry_run = args.dry_run
    confirm = args.confirm

    print(f"Action : {args.action}")
    print(f"Pool   : {args.pool}")
    print(f"Dry-run: {dry_run}")
    print(f"Confirm: {confirm}")
    if stock_code:
        print(f"Stock  : {stock_code}")
    if args.limit:
        print(f"Limit  : {args.limit}")
    print()

    summary: dict[str, int] = {}
    error_msg = ""

    try:
        if args.action == "plan":
            from src.data_repair.repair_planner import build_repair_plan
            plan = build_repair_plan(
                pool_name=args.pool,
                issue_type=args.issue_type if args.issue_type != "all" else None,
                stock_code=stock_code,
                adj=args.adj,
                limit=args.limit,
            )
            print(f"Repair plan: {len(plan)} actions")
            if not plan.empty:
                for _, row in plan.iterrows():
                    print(
                        f"  {row['stock_code']} {row['adj_type']} "
                        f"{row['repair_action']:16s} {row.get('start_date','') or '':>10s}"
                    )
            print()
            return 0

        elif args.action == "deduplicate":
            from src.data_repair.duplicate_repair import deduplicate_daily_table
            adj_types = _adj_to_list(args.adj)
            for adj_t in adj_types:
                table = "stock_daily_raw" if adj_t == "raw" else "stock_daily_qfq"
                result = deduplicate_daily_table(
                    table, stock_code=stock_code,
                    dry_run=dry_run, confirm=confirm, pool_name=args.pool,
                )
                print(f"[{adj_t}] status={result['status']} "
                      f"affected={result['affected_rows']}")
                summary[result["status"]] = summary.get(result["status"], 0) + 1

        elif args.action == "refetch":
            if not stock_code or not args.start_date or not args.end_date:
                print("[ERROR] --action refetch requires --stock-code, --start-date, --end-date")
                return 1
            from src.data_repair.date_range_repair import refetch_stock_range
            adj_types = _adj_to_list(args.adj)
            for adj_t in adj_types:
                result = refetch_stock_range(
                    stock_code, adj_t, args.start_date, args.end_date,
                    dry_run=dry_run, confirm=confirm, pool_name=args.pool,
                )
                print(f"[{adj_t}] status={result['status']} "
                      f"affected={result['affected_rows']}")
                if result.get("error_message"):
                    error_msg = result["error_message"]
                summary[result["status"]] = summary.get(result["status"], 0) + 1

        elif args.action == "rebuild-parquet":
            # Safety: real execution requires --stock-code or --limit
            if not dry_run and confirm and not stock_code and not args.limit:
                print("[ERROR] For real rebuild-parquet, please provide --stock-code or --limit.")
                return 1
            from src.data_repair.parquet_repair import (
                rebuild_all_parquet_from_duckdb,
            )
            codes = [stock_code] if stock_code else None
            summary = rebuild_all_parquet_from_duckdb(
                stock_codes=codes, adj=args.adj, limit=args.limit,
                dry_run=dry_run, confirm=confirm,
            )
            for k, v in summary.items():
                print(f"  {k}: {v}")

        elif args.action == "auto":
            from src.data_repair.repair_planner import build_repair_plan
            from src.data_repair.date_range_repair import repair_from_plan
            plan = build_repair_plan(
                pool_name=args.pool,
                issue_type=args.issue_type if args.issue_type != "all" else None,
                stock_code=stock_code,
                adj=args.adj,
                limit=args.limit,
            )
            print(f"Auto plan: {len(plan)} actions")
            if plan.empty:
                print("Nothing to repair.")
                return 0
            summary = repair_from_plan(
                plan, dry_run=dry_run, confirm=confirm,
            )
            for k in ("planned", "dry_run", "success", "failed", "skipped"):
                if k in summary:
                    print(f"  {k}: {summary[k]}")
            if "affected_rows" in summary:
                print(f"  affected_rows: {summary['affected_rows']}")

    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.warning("run_data_repair failed", exc_info=True)
        return 1

    # Summary
    print()
    print("--- Summary ---")
    if summary:
        for k, v in sorted(summary.items()):
            print(f"  {k}: {v}")
    elif args.action == "plan":
        print("  (dry-run only, no data modified)")

    if error_msg:
        print(f"  last error: {error_msg}")

    # Optional recheck
    if args.recheck and not dry_run and confirm:
        print()
        print("[INFO] Triggering V0.5 quality recheck...")
        try:
            from src.data_quality.quality_report import run_data_quality_checks
            run_data_quality_checks(
                stock_code=stock_code, adj=args.adj,
                write_to_db=True, limit=args.limit,
            )
            print("[INFO] Quality recheck complete.")
        except Exception as exc:
            print(f"[WARN] Quality recheck failed: {exc}")

    print()
    return 0


def _adj_to_list(adj: str) -> list[str]:
    if adj in ("raw", "qfq"):
        return [adj]
    return ["raw", "qfq"]


if __name__ == "__main__":
    sys.exit(main())
