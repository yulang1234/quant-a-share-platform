"""
Retry failed data updates -- re-attempt previously errored downloads.

Reads ``data_update_log`` for ``historical_load`` tasks whose status is
``"failed"`` (and that have no later ``"success"`` entry for the same
stock + adj_type combination) and re-executes them.

CLI usage::

    python -m src.data_update.retry_failed --limit 10
    python -m src.data_update.retry_failed --limit 5 --sleep 1.0
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from config.settings import ensure_dirs
from src.data_update.historical_loader import load_one_stock
from src.data_update.update_log import get_failed_tasks, get_update_summary
from src.storage.duckdb_repo import init_database

logger = logging.getLogger(__name__)


def retry_failed_tasks(
    limit: int | None = None,
    sleep_seconds: float = 0.5,
) -> dict:
    """Retry previously failed historical data loads.

    Parameters
    ----------
    limit : int, optional
        Max number of failed tasks to retry.
    sleep_seconds : float
        Seconds to sleep between requests.

    Returns
    -------
    dict
        Summary with keys: total, success, failed, total_retried, duration_seconds.
    """
    ensure_dirs()
    init_database()

    failed_df = get_failed_tasks(task_type="historical_load", limit=limit)

    if failed_df.empty:
        logger.info("No failed tasks to retry.")
        return {"total": 0, "success": 0, "failed": 0,
                "total_retried": 0, "duration_seconds": 0}

    started_at = datetime.now()

    results: list[dict] = []
    for _, row in failed_df.iterrows():
        stock_code = str(row["stock_code"])
        adj_type = str(row["adj_type"])
        start_date = str(row["start_date"]).replace("-", "") if row["start_date"] else None
        end_date = str(row["end_date"]).replace("-", "") if row["end_date"] else None

        # Use default dates if not available
        if not start_date or len(start_date) != 8:
            from src.data_update.historical_loader import _default_start_date
            start_date = _default_start_date()
        if not end_date or len(end_date) != 8:
            from src.data_update.historical_loader import _default_end_date
            end_date = _default_end_date()

        logger.info("Retrying %s (adj=%s) ...", stock_code, adj_type)
        result = load_one_stock(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adj_type=adj_type,
            sleep_seconds=sleep_seconds,
        )
        results.append(result)

    finished_at = datetime.now()
    duration = (finished_at - started_at).total_seconds()

    total_retried = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    summary = {
        "total": total_retried,
        "success": success,
        "failed": failed,
        "total_retried": total_retried,
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        "Retry complete: %d retried, %d success, %d failed, %.1f seconds",
        total_retried, success, failed, duration,
    )

    return summary


# ======================================================================
#  CLI
# ======================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Retry failed historical data loads",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of failed tasks to retry",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between requests (default: 0.5)",
    )
    return parser.parse_args(argv)


def main() -> None:
    """CLI entry point."""
    from config.logging_config import setup_logging
    setup_logging()

    args = parse_args()
    summary = retry_failed_tasks(limit=args.limit, sleep_seconds=args.sleep)

    print()
    print("=" * 60)
    print("  Retry Failed Tasks - Summary")
    print("=" * 60)
    print(f"  Total retried:  {summary['total_retried']}")
    print(f"  [OK] Success:   {summary['success']}")
    print(f"  [ERR] Failed:   {summary['failed']}")
    print(f"  Duration:       {summary['duration_seconds']}s")
    print()


if __name__ == "__main__":
    main()
