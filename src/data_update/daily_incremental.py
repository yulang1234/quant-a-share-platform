"""
Daily incremental updater -- fetch the latest trading day's data.

V1.5.7: default pool is universe_all_a.

CLI usage::

    # Full all-A run (recommended)
    python -m src.data_update.daily_incremental --pool universe_all_a --adj qfq

    # Small-batch test
    python -m src.data_update.daily_incremental --pool universe_all_a --limit 5 --adj qfq

    # Legacy core_500
    python -m src.data_update.daily_incremental --pool core_500 --limit 5 --adj raw
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta

from config.settings import ensure_dirs
from src.data_source.akshare_client import AkShareClient
from src.data_update.update_log import get_update_summary, write_update_log
from src.storage.duckdb_repo import (
    get_max_trade_date,
    init_database,
    upsert_daily_data,
)
from src.storage.parquet_repo import save_daily_parquet
from src.universe.stock_pool import get_active_stock_pool

logger = logging.getLogger(__name__)

# -- Helpers --------------------------------------------------------------

_TABLE_MAP: dict[str, str] = {
    "raw": "stock_daily_raw",
    "qfq": "stock_daily_qfq",
}


def _default_end_date() -> str:
    """Return today's date as ``"YYYYMMDD"``."""
    return datetime.now().strftime("%Y%m%d")


def _validate_date_format(date_str: str, name: str) -> str:
    """Validate a ``YYYYMMDD`` date string.

    Accepts an optional hyphenated form (``YYYY-MM-DD``) by stripping the
    dashes before length / digit checks.

    Parameters
    ----------
    date_str : str
        The candidate date string.
    name : str
        Parameter label used in the error message, e.g. ``"start_date"``.

    Returns
    -------
    str
        The normalised 8-digit ``YYYYMMDD`` string.

    Raises
    ------
    ValueError
        If *date_str* is not 8 digits after stripping hyphens.
    """
    cleaned = date_str.replace("-", "").strip()
    if len(cleaned) != 8 or not cleaned.isdigit():
        raise ValueError(
            f"Invalid {name}: '{date_str}'. Expected YYYYMMDD (8 digits)."
        )
    return cleaned


# ======================================================================
#  Core logic
# ======================================================================


def get_latest_trade_date(stock_code: str, adj_type: str) -> str | None:
    """Return the latest ``trade_date`` for *stock_code* and *adj_type*.

    Parameters
    ----------
    stock_code : str
        6-digit stock code.
    adj_type : str
        ``"raw"`` or ``"qfq"``. Any other value raises ``ValueError``.

    Returns
    -------
    str or None
        ``"YYYY-MM-DD"``, or ``None`` if no data exists.

    Raises
    ------
    ValueError
        If *adj_type* is not ``"raw"`` or ``"qfq"``.
    """
    if adj_type not in _TABLE_MAP:
        raise ValueError(
            f"Invalid adj_type: {adj_type!r}. Expected 'raw' or 'qfq'."
        )
    table = _TABLE_MAP[adj_type]
    return get_max_trade_date(table, stock_code)


def calculate_incremental_start_date(
    stock_code: str,
    adj_type: str,
    force: bool = False,
    user_start_date: str | None = None,
) -> str | None:
    """Determine the start date for an incremental fetch.

    Parameters
    ----------
    stock_code : str
    adj_type : str
    force : bool
        If ``True`` and *user_start_date* is provided, return it directly.
    user_start_date : str, optional
        ``"YYYYMMDD"``

    Returns
    -------
    str or None
        ``"YYYYMMDD"`` start date, or ``None`` if the stock has no historical
        data and we are not in force mode.
    """
    if force and user_start_date is not None:
        return user_start_date

    latest = get_latest_trade_date(stock_code, adj_type)
    if latest is None:
        return None  # no historical data

    # Add one day to the latest date
    dt = datetime.strptime(latest, "%Y-%m-%d") + timedelta(days=1)
    return dt.strftime("%Y%m%d")


def update_one_stock_incremental(
    stock_code: str,
    start_date: str,
    end_date: str,
    adj_type: str,
    sleep_seconds: float = 0.5,
) -> dict:
    """Fetch and persist incremental data for one stock and adjustment type.

    Parameters
    ----------
    stock_code : str
    start_date : str  ``"YYYYMMDD"``
    end_date : str    ``"YYYYMMDD"``
    adj_type : str    ``"raw"`` or ``"qfq"``
    sleep_seconds : float

    Returns
    -------
    dict with keys: stock_code, adj_type, status, row_count, error_message.
    """
    client = AkShareClient()
    status = "failed"
    row_count = 0
    error_message = None
    started_at = datetime.now()

    try:
        time.sleep(sleep_seconds)
        df = client.fetch_stock_daily(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            adj=adj_type,
        )

        if df is None or df.empty:
            status = "empty"
            logger.info(
                "No incremental data for %s (adj=%s, %s -> %s)",
                stock_code, adj_type, start_date, end_date,
            )
        else:
            row_count = len(df)
            table_name = _TABLE_MAP[adj_type]

            upsert_daily_data(table_name, df)
            save_daily_parquet(df, stock_code, adj_type)

            status = "success"
            logger.info(
                "%s (adj=%s): %d rows updated [%s -> %s]",
                stock_code, adj_type, row_count, start_date, end_date,
            )

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "%s (adj=%s) incremental failed: %s",
            stock_code, adj_type, error_message,
        )

    write_update_log(
        stock_code=stock_code,
        task_type="daily_incremental",
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


def run_daily_incremental(
    pool_name: str = "universe_all_a",
    limit: int | None = None,
    adj: str = "all",
    start_date: str | None = None,
    end_date: str | None = None,
    force: bool = False,
    sleep_seconds: float = 0.5,
) -> dict:
    """Run the daily incremental update for the stock pool.

    Parameters
    ----------
    pool_name : str
    limit : int, optional
    adj : str          ``"raw"``, ``"qfq"``, or ``"all"``
    start_date : str, optional  ``"YYYYMMDD"``; only used with ``--force``
    end_date : str, optional    ``"YYYYMMDD"``; defaults to today
    force : bool       If ``True``, honour *start_date* (no auto-detect)
    sleep_seconds : float

    Returns
    -------
    dict  Summary with keys: total, success, failed, empty, skipped,
          total_rows, started_at, finished_at, duration_seconds.

    Raises
    ------
    ValueError
        - If *end_date* is provided but not a valid ``YYYYMMDD``.
        - If ``force=True`` but *start_date* is ``None``.
        - If ``force=True`` and *start_date* is later than *end_date*.
        - If ``force=False`` but a manual *start_date* is supplied.
        - If *start_date* (in force mode) is not a valid ``YYYYMMDD``.
    """
    # ── Parameter validation (before any IO) ───────────────────────────
    s_date = _validate_date_format(end_date, "end_date") if end_date else _default_end_date()

    if force and start_date is None:
        raise ValueError("force=True requires --start-date. Pass --start-date to override.")
    if start_date is not None and not force:
        raise ValueError(
            "Manual start_date requires --force. Pass --force to override."
        )
    if force and start_date is not None:
        start_date = _validate_date_format(start_date, "start_date")
        if start_date > s_date:
            raise ValueError(
                f"start_date ({start_date}) cannot be later than end_date ({s_date})."
            )

    started_at = datetime.now()

    ensure_dirs()
    init_database()

    # Stock list
    pool_df = get_active_stock_pool(pool_name)
    if pool_df.empty:
        logger.warning("Stock pool '%s' is empty -- nothing to do.", pool_name)
        return {"total": 0, "success": 0, "failed": 0, "empty": 0,
                "skipped": 0, "total_rows": 0, "started_at": started_at,
                "finished_at": datetime.now(), "duration_seconds": 0}

    stock_codes = pool_df["stock_code"].tolist()
    if limit is not None and limit > 0:
        stock_codes = stock_codes[:limit]

    # Determine adj types
    if adj == "all":
        adj_types = ["raw", "qfq"]
    elif adj in ("raw", "qfq"):
        adj_types = [adj]
    else:
        raise ValueError(f"adj must be 'raw', 'qfq', or 'all', got '{adj}'")

    logger.info(
        "Daily incremental start: %d stocks, adj=%s, force=%s, end=%s",
        len(stock_codes), adj, force, s_date,
    )

    results: list[dict] = []
    for code in stock_codes:
        for adj_type in adj_types:
            # Per-(stock, adj) task timestamps so skipped / empty logs
            # carry their own time, not the whole-run start time.
            task_started = datetime.now()

            # Calculate start date
            calc_start = calculate_incremental_start_date(
                stock_code=code,
                adj_type=adj_type,
                force=force,
                user_start_date=start_date,
            )

            if calc_start is None:
                # No historical data -- skip
                logger.info(
                    "%s (adj=%s) has no historical data -- skipped",
                    code, adj_type,
                )
                task_finished = datetime.now()
                write_update_log(
                    stock_code=code,
                    task_type="daily_incremental",
                    adj_type=adj_type,
                    start_date=s_date,
                    end_date=s_date,
                    row_count=0,
                    status="skipped",
                    error_message="No historical data; run V0.3 first",
                    started_at=task_started,
                    finished_at=task_finished,
                )
                results.append({
                    "stock_code": code,
                    "adj_type": adj_type,
                    "status": "skipped",
                    "row_count": 0,
                    "error_message": None,
                })
                continue

            if calc_start > s_date:
                # Already up to date -- log the real latest trade date,
                # not the (max+1) calculated start that misleads readers.
                latest = get_latest_trade_date(code, adj_type)
                logger.info(
                    "%s (adj=%s) already up to date "
                    "(latest_trade_date=%s, end_date=%s) -- skipped",
                    code, adj_type, latest, s_date,
                )
                task_finished = datetime.now()
                write_update_log(
                    stock_code=code,
                    task_type="daily_incremental",
                    adj_type=adj_type,
                    start_date=calc_start,
                    end_date=s_date,
                    row_count=0,
                    status="skipped",
                    error_message="Already up to date",
                    started_at=task_started,
                    finished_at=task_finished,
                )
                results.append({
                    "stock_code": code,
                    "adj_type": adj_type,
                    "status": "skipped",
                    "row_count": 0,
                    "error_message": None,
                })
                continue

            result = update_one_stock_incremental(
                stock_code=code,
                start_date=calc_start,
                end_date=s_date,
                adj_type=adj_type,
                sleep_seconds=sleep_seconds,
            )
            results.append(result)

    # Summary
    finished_at = datetime.now()
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    empty = sum(1 for r in results if r["status"] == "empty")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    total_rows = sum(r["row_count"] for r in results)
    duration = (finished_at - started_at).total_seconds()

    summary = {
        "total": total,
        "success": success,
        "failed": failed,
        "empty": empty,
        "skipped": skipped,
        "total_rows": total_rows,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        "Daily incremental complete: %d total, %d success, "
        "%d failed, %d empty, %d skipped, %d rows, %.1f seconds",
        total, success, failed, empty, skipped, total_rows, duration,
    )

    return summary


# ======================================================================
#  CLI
# ======================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Daily incremental update for A-share daily data",
    )
    parser.add_argument(
        "--pool", default="universe_all_a",
        help="Stock pool name (default: universe_all_a)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of stocks to process (for testing)",
    )
    parser.add_argument(
        "--adj", choices=["raw", "qfq", "all"], default="all",
        help="Adjustment type: raw, qfq, or all (default: all)",
    )
    parser.add_argument(
        "--start-date", default=None,
        help="Start date YYYYMMDD (requires --force)",
    )
    parser.add_argument(
        "--end-date", default=None,
        help="End date YYYYMMDD (default: today)",
    )
    parser.add_argument(
        "--sleep", type=float, default=0.5,
        help="Seconds to sleep between requests (default: 0.5)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-fetch using the specified --start-date",
    )
    return parser.parse_args(argv)


def main() -> None:
    """CLI entry point."""
    from config.logging_config import setup_logging
    setup_logging()

    args = parse_args()

    try:
        summary = run_daily_incremental(
            pool_name=args.pool,
            limit=args.limit,
            adj=args.adj,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force,
            sleep_seconds=args.sleep,
        )
    except ValueError as e:
        # Date/parameter validation failure: print a short ASCII message
        # and exit WITHOUT a traceback.
        print()
        print(f"[ERROR] {e}")
        print()
        raise SystemExit(1)

    # ASCII-safe print summary
    print()
    print("=" * 60)
    print("  Daily Incremental Update - Summary")
    print("=" * 60)
    print(f"  Total tasks:   {summary['total']}")
    print(f"  [OK] Success:  {summary['success']}")
    print(f"  [ERR] Failed:  {summary['failed']}")
    print(f"  [WARN] Empty:  {summary['empty']}")
    print(f"  [SKIP] Skipped:{summary['skipped']}")
    print(f"  Total rows:    {summary['total_rows']}")
    print(f"  Started:       {summary['started_at']}")
    print(f"  Finished:      {summary['finished_at']}")
    print(f"  Duration:      {summary['duration_seconds']}s")
    print()

    # DB summary per task type
    db_summary = get_update_summary(task_type="daily_incremental")
    print(f"  DB summary (daily_incremental): "
          f"success={db_summary['success']}, "
          f"failed={db_summary['failed']}, "
          f"empty={db_summary['empty']}, "
          f"skipped={db_summary['skipped']}")


if __name__ == "__main__":
    main()
