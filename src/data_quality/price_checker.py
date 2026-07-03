"""
Price sanity checker — detect abnormal OHLCV values in daily data.

V0.5: rule-based checks that never mutate the input DataFrame.
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


def _build_reasons(row: pd.Series) -> list[str]:
    """Collect all price-anomaly reasons for a single row."""
    reasons: list[str] = []

    price_cols = ["open", "high", "low", "close"]
    for col in price_cols:
        if col in row and pd.notna(row[col]) and row[col] <= 0:
            reasons.append(f"{col} <= 0")

    if "high" in row and "low" in row and pd.notna(row["high"]) and pd.notna(row["low"]):
        if row["high"] < row["low"]:
            reasons.append("high < low")
        if "open" in row and pd.notna(row["open"]) and row["high"] < row["open"]:
            reasons.append("high < open")
        if "close" in row and pd.notna(row["close"]) and row["high"] < row["close"]:
            reasons.append("high < close")
        if "open" in row and pd.notna(row["open"]) and row["low"] > row["open"]:
            reasons.append("low > open")
        if "close" in row and pd.notna(row["close"]) and row["low"] > row["close"]:
            reasons.append("low > close")

    if "volume" in row and pd.notna(row["volume"]) and row["volume"] < 0:
        reasons.append("volume < 0")
    if "amount" in row and pd.notna(row["amount"]) and row["amount"] < 0:
        reasons.append("amount < 0")

    return reasons


def check_price_anomalies(
    stock_code: str | None = None,
    adj_type: str = "raw",
) -> pd.DataFrame:
    """Flag rows where price/volume fields violate basic business rules.

    Checks performed:
    - any of ``open/high/low/close`` <= 0
    - ``high < low``
    - ``high < open`` or ``high < close``
    - ``low > open`` or ``low > close``
    - ``volume < 0``
    - ``amount < 0``

    Parameters
    ----------
    stock_code : str, optional
        6-digit stock code.  If ``None``, check all stocks.
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``stock_code``, ``trade_date``, ``adj_type``,
        ``issue_type``, ``issue_level``, ``issue_detail``.
    """
    table = _validate_adj_type(adj_type)
    params: list[str] = []
    where_clause = ""
    if stock_code is not None:
        code = validate_stock_code(stock_code)
        where_clause = "WHERE stock_code = ?"
        params.append(code)

    sql = f"""
        SELECT stock_code, trade_date, open, high, low, close, volume, amount
        FROM {table}
        {where_clause}
        ORDER BY stock_code, trade_date
    """
    df = query_df(sql, params if params else None)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "stock_code",
                "trade_date",
                "adj_type",
                "issue_type",
                "issue_level",
                "issue_detail",
            ]
        )

    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")

    records: list[dict] = []
    for _, row in df.iterrows():
        reasons = _build_reasons(row)
        if reasons:
            records.append(
                {
                    "stock_code": row["stock_code"],
                    "trade_date": row["trade_date"],
                    "adj_type": adj_type,
                    "issue_type": "price_anomaly",
                    "issue_level": "high",
                    "issue_detail": "; ".join(reasons),
                }
            )

    return pd.DataFrame(records)
