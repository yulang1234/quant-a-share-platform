"""
Return calculator — stock returns and portfolio daily returns.

V1.1: qfq close-based returns.
"""

from __future__ import annotations

import pandas as pd

from src.storage.duckdb_repo import query_df


def get_price_data(stock_codes: list[str] | None, start_date=None, end_date=None) -> pd.DataFrame:
    if not stock_codes:
        return pd.DataFrame()
    codes = [str(c).zfill(6) for c in stock_codes]
    placeholders = ",".join(["?"] * len(codes))
    conds = [f"stock_code IN ({placeholders})"]
    params = list(codes)
    if start_date:
        conds.append("trade_date >= ?"); params.append(start_date)
    if end_date:
        conds.append("trade_date <= ?"); params.append(end_date)
    try:
        return query_df(f"SELECT stock_code, trade_date, close FROM stock_daily_qfq WHERE {' AND '.join(conds)} ORDER BY stock_code, trade_date", params)
    except Exception:
        return pd.DataFrame()


def calculate_stock_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame(columns=["stock_code", "trade_date", "stock_return"])
    df = price_df[["stock_code", "trade_date", "close"]].copy()
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])
    df["stock_return"] = df.groupby("stock_code")["close"].pct_change().fillna(0)
    return df[["stock_code", "trade_date", "stock_return"]]


def calculate_portfolio_daily_returns(position_df: pd.DataFrame, stock_return_df: pd.DataFrame) -> pd.DataFrame:
    if position_df.empty or stock_return_df.empty:
        return pd.DataFrame(columns=["trade_date", "portfolio_return", "holding_count"])

    pos = position_df[["trade_date", "stock_code", "weight"]].copy()
    ret = stock_return_df[["stock_code", "trade_date", "stock_return"]].copy()

    pos["trade_date"] = pd.to_datetime(pos["trade_date"])
    ret["trade_date"] = pd.to_datetime(ret["trade_date"])
    pos["stock_code"] = pos["stock_code"].astype(str).str.zfill(6)
    ret["stock_code"] = ret["stock_code"].astype(str).str.zfill(6)

    merged = pos.merge(ret, on=["trade_date", "stock_code"], how="left")
    merged["stock_return"] = merged["stock_return"].fillna(0)
    merged["weighted"] = merged["weight"] * merged["stock_return"]

    agg = merged.groupby("trade_date").agg(
        portfolio_return=("weighted", "sum"),
        holding_count=("stock_code", "count"),
    ).reset_index()
    return agg
