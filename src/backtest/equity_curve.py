"""
Equity curve — basic NAV calculation from portfolio returns.

V1.1: equity = initial_cash * cumprod(1 + return)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_equity_curve(daily_return_df: pd.DataFrame, initial_cash: float = 1_000_000) -> pd.DataFrame:
    if daily_return_df.empty or "trade_date" not in daily_return_df.columns:
        return pd.DataFrame(columns=["trade_date", "initial_cash", "portfolio_return", "equity"])

    df = daily_return_df[["trade_date", "portfolio_return"]].copy()
    if "holding_count" in daily_return_df.columns:
        df["holding_count"] = daily_return_df["holding_count"]
    df = df.sort_values("trade_date")
    df["portfolio_return"] = df["portfolio_return"].fillna(0)
    df["initial_cash"] = initial_cash
    df["equity"] = initial_cash * (1 + df["portfolio_return"]).cumprod()
    return df[["trade_date", "initial_cash", "portfolio_return", "equity"]]
