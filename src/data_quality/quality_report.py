"""
Quality report generator — aggregate all data-quality checks.

V0.5: orchestrates duplicate, missing-date and price checks, writes the
results to ``data_quality_report``, and exposes a CLI entry point.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

import pandas as pd

from src.data_quality.duplicate_checker import check_duplicate_daily_data
from src.data_quality.missing_date_checker import check_missing_trade_dates
from src.data_quality.price_checker import check_price_anomalies
from src.storage.duckdb_repo import (
    count_quality_issues,
    insert_quality_report,
    query_df,
)
from src.universe.stock_pool import get_active_stock_pool, validate_stock_code

logger = logging.getLogger(__name__)

_ADJ_OPTIONS = {"raw", "qfq", "all"}


def _today_str() -> str:
    """Return today's date as ``YYYY-MM-DD``."""
    return datetime.now().strftime("%Y-%m-%d")


def _deduplicate_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Drop identical issue records within the same batch."""
    if df.empty:
        return df
    df = df.copy()
    df["_dedup_key"] = df.apply(
        lambda r: (
            f"{r['start_date']}|{r['end_date']}"
            if pd.notna(r.get("start_date")) and pd.notna(r.get("end_date"))
            else str(r.get("trade_date"))
        ),
        axis=1,
    )
    df = df.drop_duplicates(
        subset=["stock_code", "issue_type", "adj_type", "_dedup_key"]
    )
    return df.drop(columns=["_dedup_key"])


def run_data_quality_checks(
    stock_code: str | None = None,
    adj: str = "all",
    write_to_db: bool = True,
    limit: int | None = None,
) -> dict:
    """Run all quality checks and optionally persist the results.

    Parameters
    ----------
    stock_code : str, optional
        6-digit stock code.  If provided, ``limit`` is ignored.
    adj : str
        ``"raw"``, ``"qfq"`` or ``"all"``.
    write_to_db : bool
        If ``True``, insert issue records into ``data_quality_report``.
    limit : int, optional
        Maximum number of active stocks to check when ``stock_code`` is
        ``None``.

    Returns
    -------
    dict
        Summary with keys: ``total_issues``, ``duplicate_issues``,
        ``missing_date_issues``, ``price_issues``, ``raw_issues``,
        ``qfq_issues``, ``checked_stocks``.
    """
    if adj not in _ADJ_OPTIONS:
        raise ValueError(
            f"Invalid adj: {adj!r}. Expected 'raw', 'qfq' or 'all'."
        )

    adj_list = ["raw", "qfq"] if adj == "all" else [adj]

    if stock_code is not None:
        codes = [validate_stock_code(stock_code)]
    else:
        pool = get_active_stock_pool()
        if limit is not None:
            pool = pool.head(limit)
        codes = (
            pool["stock_code"].astype(str).tolist() if not pool.empty else []
        )

    frames: list[pd.DataFrame] = []
    for adj_type in adj_list:
        for code in codes:
            frames.append(check_duplicate_daily_data(code, adj_type))
            frames.append(check_missing_trade_dates(code, adj_type))
            frames.append(check_price_anomalies(code, adj_type))

    issues = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    issues = _deduplicate_issues(issues)

    if write_to_db and not issues.empty:
        insert_df = issues.copy()
        insert_df["check_date"] = _today_str()
        insert_df["status"] = "open"
        insert_quality_report(insert_df)

    summary = {
        "total_issues": len(issues),
        "duplicate_issues": int(
            (issues["issue_type"] == "duplicate_record").sum()
        ),
        "missing_date_issues": int(
            (issues["issue_type"] == "missing_trade_date").sum()
        ),
        "price_issues": int(
            (issues["issue_type"] == "price_anomaly").sum()
        ),
        "raw_issues": int((issues["adj_type"] == "raw").sum()),
        "qfq_issues": int((issues["adj_type"] == "qfq").sum()),
        "checked_stocks": len(codes),
    }
    return summary


def get_recent_quality_issues(limit: int = 100) -> pd.DataFrame:
    """Return the most recent rows from ``data_quality_report``."""
    return query_df(
        """
        SELECT *
        FROM data_quality_report
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        [limit],
    )


def get_quality_issue_summary() -> dict:
    """Return aggregate counts of open quality issues."""
    df = query_df(
        """
        SELECT issue_type, adj_type, COUNT(*) AS issue_count
        FROM data_quality_report
        WHERE status = 'open'
        GROUP BY issue_type, adj_type
        ORDER BY issue_type, adj_type
        """
    )
    total = int(df["issue_count"].sum()) if not df.empty else 0
    return {
        "total_open_issues": total,
        "by_type_adj": df.to_dict("records"),
    }


# ==============================================================================
#  CLI
# ==============================================================================

def _print_summary(summary: dict) -> None:
    """Print an ASCII-safe summary to stdout."""
    print("")
    print("=" * 56)
    print("  Data Quality Check - Summary")
    print("=" * 56)
    print(f"  Checked stocks:    {summary['checked_stocks']}")
    print(f"  Total issues:      {summary['total_issues']}")
    print(f"  Duplicate issues:  {summary['duplicate_issues']}")
    print(f"  Missing dates:     {summary['missing_date_issues']}")
    print(f"  Price anomalies:   {summary['price_issues']}")
    print(f"  Raw issues:        {summary['raw_issues']}")
    print(f"  QFQ issues:        {summary['qfq_issues']}")
    print("=" * 56)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``python -m src.data_quality.quality_report``."""
    parser = argparse.ArgumentParser(
        description="Run data quality checks for daily market data."
    )
    parser.add_argument(
        "--adj",
        default="all",
        help="Adjustment type to check: raw, qfq or all (default: all).",
    )
    parser.add_argument(
        "--stock-code",
        type=str,
        default=None,
        help="Check a single 6-digit stock code.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of stocks to check.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run checks without writing results to the database.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_data_quality_checks(
            stock_code=args.stock_code,
            adj=args.adj,
            write_to_db=not args.no_write,
            limit=args.limit,
        )
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1

    _print_summary(summary)
    if args.no_write:
        print("  [INFO] Results were not written to the database (--no-write).")
    else:
        print("  [INFO] Results written to data_quality_report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
