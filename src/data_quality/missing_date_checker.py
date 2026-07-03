"""
Missing-date checker — find gaps in a stock's daily data series.

V0.5: simplified natural-day gap detection (no external trading calendar).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd

from src.storage.duckdb_repo import query_df
from src.universe.stock_pool import validate_stock_code

logger = logging.getLogger(__name__)

_TABLE_MAP: dict[str, str] = {
    "raw": "stock_daily_raw",
    "qfq": "stock_daily_qfq",
}


def _validate_adj_type(adj_type: str) -> str:
    """Return the DuckDB table name for *adj_type* or raise ``ValueError``."""
    if adj_type not in _TABLE_MAP:
        raise ValueError(
            f"Invalid adj_type: {adj_type!r}. Expected 'raw' or 'qfq'."
        )
    return _TABLE_MAP[adj_type]


def check_missing_trade_dates(
    stock_code: str | None = None,
    adj_type: str = "raw",
) -> pd.DataFrame:
    """Detect natural-day gaps in the stored daily series for each stock.

    A gap is reported when the difference between two consecutive stored
    trading dates is greater than one calendar day.  The missing interval
    is reported as ``[next_date - 1 day, previous_date + 1 day]`` — i.e.
    the range of calendar days that have no record.

    Parameters
    ----------
    stock_code : str, optional
        6-digit stock code.  If ``None``, check all stocks.
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``stock_code``, ``start_date``, ``end_date``,
        ``missing_days``, ``adj_type``, ``issue_type``, ``issue_level``,
        ``issue_detail``.
    """
    table = _validate_adj_type(adj_type)
    params: list[str] = []
    where_clause = ""
    if stock_code is not None:
        code = validate_stock_code(stock_code)
        where_clause = "WHERE stock_code = ?"
        params.append(code)

    sql = f"""
        SELECT DISTINCT stock_code, trade_date
        FROM {table}
        {where_clause}
        ORDER BY stock_code, trade_date
    """
    df = query_df(sql, params if params else None)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "stock_code",
                "start_date",
                "end_date",
                "missing_days",
                "adj_type",
                "issue_type",
                "issue_level",
                "issue_detail",
            ]
        )

    df["trade_date"] = pd.to_datetime(df["trade_date"])

    records: list[dict] = []
    for code, group in df.groupby("stock_code"):
        if len(group) < 2:
            continue
        dates = group["trade_date"].sort_values().reset_index(drop=True)
        prev = dates.iloc[0]
        for cur in dates.iloc[1:]:
            delta = (cur - prev).days
            if delta > 1:
                gap_start = prev + timedelta(days=1)
                gap_end = cur - timedelta(days=1)
                missing_days = delta - 1
                records.append(
                    {
                        "stock_code": code,
                        "start_date": gap_start.strftime("%Y-%m-%d"),
                        "end_date": gap_end.strftime("%Y-%m-%d"),
                        "missing_days": missing_days,
                        "adj_type": adj_type,
                        "issue_type": "missing_trade_date",
                        "issue_level": "medium",
                        "issue_detail": (
                            f"Missing trading dates between {prev.strftime('%Y-%m-%d')} "
                            f"and {cur.strftime('%Y-%m-%d')} ({missing_days} calendar day(s))"
                        ),
                    }
                )
            prev = cur

    return pd.DataFrame(records)
