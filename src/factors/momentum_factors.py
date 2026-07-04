"""
Momentum factor calculations — N-day price momentum.

V0.7: momentum_Nd = close / close.shift(N) - 1
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import validate_factor_input


def calculate_momentum_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate momentum_Nd factors."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date"]].copy()

    for n in (5, 10, 20, 60):
        shifted = df.groupby("stock_code")["close"].shift(n)
        result[f"momentum_{n}d"] = (df["close"] / shifted) - 1

    return result
