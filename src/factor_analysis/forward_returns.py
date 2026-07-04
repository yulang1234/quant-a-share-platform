"""
Forward returns calculation for factor effectiveness analysis.

V0.9: forward_return_Nd = close.shift(-N) / close - 1
"""

from __future__ import annotations

import pandas as pd

from src.storage.duckdb_repo import query_df, upsert_forward_returns


def calculate_forward_returns(price_df: pd.DataFrame, forward_days: int = 5) -> pd.DataFrame:
    """Calculate forward returns from price data.

    Parameters
    ----------
    price_df : pd.DataFrame
        Must contain stock_code, trade_date, close.
    forward_days : int
        Number of days to look ahead.

    Returns
    -------
    pd.DataFrame
        Columns: stock_code, trade_date, forward_days, close, future_close, forward_return.
    """
    if price_df is None or price_df.empty:
        return pd.DataFrame(columns=["stock_code", "trade_date", "forward_days", "close", "future_close", "forward_return"])

    df = price_df[["stock_code", "trade_date", "close"]].copy()
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])

    df["future_close"] = df.groupby("stock_code")["close"].shift(-forward_days)
    df["forward_return"] = df["future_close"] / df["close"] - 1
    df["forward_days"] = forward_days

    # Replace inf with NaN
    df["forward_return"] = df["forward_return"].replace([float("inf"), float("-inf")], float("nan"))

    return df[["stock_code", "trade_date", "forward_days", "close", "future_close", "forward_return"]].reset_index(drop=True)


def get_price_data_for_forward_returns(
    stock_codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    forward_days: int = 5,
    limit: int | None = None,
) -> pd.DataFrame:
    """Read close prices from stock_daily_qfq.

    When *end_date* is provided, the read range is extended by
    ``forward_days * 3`` calendar days so that ``forward_return`` near
    the boundary has enough future data to compute (weekends/holidays).
    """
    conditions = ["1=1"]
    params: list = []
    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)

    # Extend end_date to cover forward look-ahead
    read_end = end_date
    if end_date:
        import datetime as _dt
        try:
            ed = _dt.datetime.strptime(end_date.replace("-", ""), "%Y%m%d")
            ed = ed + _dt.timedelta(days=forward_days * 3)
            read_end = ed.strftime("%Y-%m-%d")
        except Exception:
            pass
        conditions.append("trade_date <= ?")
        params.append(read_end)
    elif end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    if stock_codes and len(stock_codes) > 0:
        if limit:
            stock_codes = stock_codes[:limit]
        placeholders = ",".join(["?"] * len(stock_codes))
        conditions.append(f"stock_code IN ({placeholders})")
        params.extend(stock_codes)

    where = " AND ".join(conditions)
    sql = f"SELECT stock_code, trade_date, close FROM stock_daily_qfq WHERE {where} ORDER BY stock_code, trade_date"
    if limit and not stock_codes:
        sql += f" LIMIT {int(limit) * 100}"

    try:
        return query_df(sql, params)
    except Exception:
        return pd.DataFrame()


def save_forward_returns(forward_df: pd.DataFrame) -> int:
    return upsert_forward_returns(forward_df)
