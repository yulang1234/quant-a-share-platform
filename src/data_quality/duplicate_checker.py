"""
Duplicate-checker — detect duplicate (stock_code, trade_date) rows in daily data.

V0.5: SQL-based GROUP BY check against ``stock_daily_raw`` / ``stock_daily_qfq``.
"""

from __future__ import annotations

import logging

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


def check_duplicate_daily_data(
    stock_code: str | None = None,
    adj_type: str = "raw",
) -> pd.DataFrame:
    """Find duplicate ``(stock_code, trade_date)`` rows in a daily table.

    Parameters
    ----------
    stock_code : str, optional
        6-digit stock code.  If ``None``, check all stocks in the table.
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``stock_code``, ``trade_date``, ``duplicate_count``,
        ``adj_type``, ``issue_type``, ``issue_level``, ``issue_detail``.
        Empty if no duplicates are found.
    """
    table = _validate_adj_type(adj_type)
    params: list[str] = []

    where_clause = ""
    if stock_code is not None:
        code = validate_stock_code(stock_code)
        where_clause = "WHERE stock_code = ?"
        params.append(code)

    sql = f"""
        SELECT
            stock_code,
            trade_date,
            COUNT(*) AS duplicate_count
        FROM {table}
        {where_clause}
        GROUP BY stock_code, trade_date
        HAVING COUNT(*) > 1
        ORDER BY stock_code, trade_date
    """
    df = query_df(sql, params if params else None)
    if df.empty:
        return df

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    df["adj_type"] = adj_type
    df["issue_type"] = "duplicate_record"
    df["issue_level"] = "high"
    df["issue_detail"] = df["duplicate_count"].apply(
        lambda n: f"Duplicate record count: {n}"
    )

    return df[
        [
            "stock_code",
            "trade_date",
            "duplicate_count",
            "adj_type",
            "issue_type",
            "issue_level",
            "issue_detail",
        ]
    ]
