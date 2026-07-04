"""
Volatility factor calculations — rolling std of daily returns.

V0.7: full implementation.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import validate_factor_input


def calculate_volatility_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate volatility_Nd factors: rolling std of return_1d."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date"]].copy()

    # Compute return_1d if not present
    if "return_1d" not in df.columns:
        result["return_1d"] = df.groupby("stock_code")["close"].pct_change()
    else:
        result["return_1d"] = df["return_1d"]

    for n in (5, 10, 20, 60):
        result[f"volatility_{n}d"] = (
            result.groupby("stock_code")["return_1d"]
            .transform(lambda x: x.rolling(n, min_periods=n).std())
        )

    return result.drop(columns=["return_1d"])
