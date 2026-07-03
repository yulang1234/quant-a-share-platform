"""
Historical data loader -- batch-load up to 20 years of daily data per stock.

This is the V0.3 core module.  It reads active stocks from the stock pool
and fetches historical daily K-line data via AkShare, then persists both
raw and forward-adjusted data to DuckDB and Parquet.

CLI usage::

    # Full run (500 stocks, raw + qfq)
    python -m src.data_update.historical_loader --pool core_500 --adj all

    # Small-batch test (5 stocks, raw only)
    python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj raw

    # Custom date range
    python -m src.data_update.historical_loader --pool core_500 --start-date 20200101 --end-date 20231231 --limit 3
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

from config.settings import ensure_dirs
from src.data_source.akshare_client import AkShareClient
from src.data_update.update_log import get_update_summary, write_update_log
from src.storage.duckdb_repo import init_database, upsert_daily_data
from src.storage.parquet_repo import read_daily_parquet, save_daily_parquet
from src.universe.stock_pool import get_active_stock_pool

logger = logging.getLogger(__name__)

# -- Constants --------------------------------------------------------------
DEFAULT_START_YEARS = 20  # 20 years back from today


def _default_start_date() -> str:
    """Return ``"YYYYMMDD"`` for 20 years before today."""
    d = datetime.now() - timedelta(days=365 * DEFAULT_START_YEARS)
    return d.strftime("%Y%m%d")


def _default_end_date() -> str:
    """Return today's date as ``"YYYYMMDD"``."""
    return datetime.now().strftime("%Y%m%d")


# ======================================================================
#  Core load functions
# ======================================================================


def load_one_stock(
    stock_code: str,
    start_date: str,
    end_date: str,
    adj_type: str,
    sleep_seconds: float = 0.5,
) -> dict:
    """Load historical data for a single stock with one adjustment type.

    This is the atomic unit of work -- it fetches, persists, and logs.

    Parameters
    ----------
    stock_code : str
        6-digit stock code.
    start_date : str
        ``"YYYYMMDD"``
    end_date : str
        ``"YYYYMMDD"``
    adj_type : str
        ``"raw"`` or ``"qfq"``.
    sleep_seconds : float
        Seconds to wait after the request (rate limiting).

    Returns
    -------
    dict
        Keys: stock_code, adj_type, status, row_count, error_message.
    """
    client = AkShareClient()
    status = "failed"
    row_count = 0
    error_message = None
    started_at = datetime.now()

    try:
        # -- Fetch ---------------------------------------------------------
        time.sleep(sleep_seconds)
        df = client.fetch_stock_daily(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adj=adj_type,
        )

        if df is None or df.empty:
            status = "empty"
            logger.info("No data for %s (adj=%s) -- empty result", stock_code, adj_type)
        else:
            row_count = len(df)

            # Determine the target table name
            table_name = "stock_daily_raw" if adj_type == "raw" else "stock_daily_qfq"

            # -- DuckDB ------------------------------------------------
            upsert_daily_data(table_name, df)

            # -- Parquet -----------------------------------------------
            save_daily_parquet(df, stock_code, adj_type)

            status = "success"
            logger.info(
                "%s (adj=%s): %d rows loaded", stock_code, adj_type, row_count
            )

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "%s (adj=%s) failed: %s", stock_code, adj_type, error_message
        )

    # -- Write log -----------------------------------------------------
    write_update_log(
        stock_code=stock_code,
        task_type="historical_load",
        adj_type=adj_type,
        start_date=start_date,
        end_date=end_date,
        row_count=row_count,
        status=status,
        error_message=error_message,
        started_at=started_at,
        finished_at=datetime.now(),
    )

    return {
        "stock_code": stock_code,
        "adj_type": adj_type,
        "status": status,
        "row_count": row_count,
        "error_message": error_message,
    }


def load_historical_data(
    pool_name: str = "core_500",
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    adj: str = "all",
    sleep_seconds: float = 0.5,
) -> dict:
    """Load historical daily data for stocks in a pool.

    Parameters
    ----------
    pool_name : str
        Stock pool name (default ``"core_500"``).
    start_date : str, optional
        ``"YYYYMMDD"``.  Defaults to 20 years before today.
    end_date : str, optional
        ``"YYYYMMDD"``.  Defaults to today.
    limit : int, optional
        If set, only process the first *limit* stocks (for testing).
    adj : str
        ``"raw"`` -- raw only, ``"qfq"`` -- QFQ only, ``"all"`` -- both.
    sleep_seconds : float
        Seconds to sleep between requests.

    Returns
    -------
    dict
        Summary with keys: total, success, failed, empty, total_rows,
        started_at, finished_at, duration_seconds.
    """
    s_date = start_date or _default_start_date()
    e_date = end_date or _default_end_date()
    started_at = datetime.now()

    # -- 1. Init -------------------------------------------------------
    ensure_dirs()
    init_database()

    # -- 2. Get stock list ---------------------------------------------
    pool_df = get_active_stock_pool(pool_name)
    if pool_df.empty:
        logger.warning("Stock pool '%s' is empty -- nothing to load.", pool_name)
        return {"total": 0, "success": 0, "failed": 0, "empty": 0,
                "total_rows": 0, "started_at": started_at,
                "finished_at": datetime.now(), "duration_seconds": 0}

    stock_codes = pool_df["stock_code"].tolist()
    if limit is not None and limit > 0:
        stock_codes = stock_codes[:limit]

    # Determine which adj types to run
    adj_types: list[str]
    if adj == "all":
        adj_types = ["raw", "qfq"]
    elif adj in ("raw", "qfq"):
        adj_types = [adj]
    else:
        raise ValueError(f"adj must be 'raw', 'qfq', or 'all', got '{adj}'")

    logger.info(
        "Starting historical load: %d stocks, adj=%s, %s -> %s",
        len(stock_codes), adj, s_date, e_date,
    )

    # -- 3. Process each stock -----------------------------------------
    results: list[dict] = []
    for code in stock_codes:
        for adj_type in adj_types:
            result = load_one_stock(code, s_date, e_date, adj_type, sleep_seconds)
            results.append(result)

    # -- 4. Summary ----------------------------------------------------
    finished_at = datetime.now()
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    empty = sum(1 for r in results if r["status"] == "empty")
    total_rows = sum(r["row_count"] for r in results)

    duration = (finished_at - started_at).total_seconds()

    summary = {
        "total": total,
        "success": success,
        "failed": failed,
        "empty": empty,
        "total_rows": total_rows,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        "Historical load complete: %d total, %d success, %d failed, "
        "%d empty, %d rows, %.1f seconds",
        total, success, failed, empty, total_rows, duration,
    )

    return summary


# ======================================================================
#  CLI
# ======================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Load historical A-share daily data from AkShare",
    )
    parser.add_argument(
        "--pool",
        default="core_500",
        help="Stock pool name (default: core_500)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date YYYYMMDD (default: 20 years ago)",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date YYYYMMDD (default: today)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of stocks to process (for testing)",
    )
    parser.add_argument(
        "--adj",
        choices=["raw", "qfq", "all"],
        default="all",
        help="Adjustment type: raw, qfq, or all (default: all)",
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
    summary = load_historical_data(
        pool_name=args.pool,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        adj=args.adj,
        sleep_seconds=args.sleep,
    )

    # Pretty-print summary (ASCII-safe only)
    print()
    print("=" * 60)
    print("  Historical Data Load - Summary")
    print("=" * 60)
    print(f"  Total tasks:   {summary['total']}")
    print(f"  [OK] Success:  {summary['success']}")
    print(f"  [ERR] Failed:  {summary['failed']}")
    print(f"  [WARN] Empty:  {summary['empty']}")
    print(f"  Total rows:    {summary['total_rows']}")
    print(f"  Started:       {summary['started_at']}")
    print(f"  Finished:      {summary['finished_at']}")
    print(f"  Duration:      {summary['duration_seconds']}s")
    print()

    # Also show update summary from DB
    db_summary = get_update_summary(task_type="historical_load")
    print(f"  DB summary:  success={db_summary['success']}, "
          f"failed={db_summary['failed']}, "
          f"empty={db_summary['empty']}")
    print()


if __name__ == "__main__":
    main()
