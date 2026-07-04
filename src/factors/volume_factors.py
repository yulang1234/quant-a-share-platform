"""
Volume-based factor calculations — volume/amount/turnover moving averages.

V0.7: full implementation.  Gracefully handles missing columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base_factor import safe_divide, validate_factor_input


def _ma_of(df: pd.DataFrame, col: str, n: int) -> pd.Series:
    """N-period rolling mean of *col* within each stock_code group."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby("stock_code")[col].transform(
        lambda x: x.rolling(n, min_periods=n).mean()
    )


def calculate_volume_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate volume and amount moving average factors."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date"]].copy()

    for n in (5, 20, 60):
        result[f"volume_ma{n}"] = _ma_of(df, "volume", n)
        result[f"amount_ma{n}"] = _ma_of(df, "amount", n)

    result["volume_ratio_5_20"] = safe_divide(
        result["volume_ma5"], result["volume_ma20"]
    )
    result["volume_ratio_20_60"] = safe_divide(
        result["volume_ma20"], result["volume_ma60"]
    )

    return result


def calculate_turnover_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate turnover-rate moving average factors.

    Gracefully returns NaN columns when turnover_rate is missing.
    """
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date"]].copy()

    for n in (5, 20, 60):
        result[f"turnover_ma{n}"] = _ma_of(df, "turnover_rate", n)

    result["turnover_ratio_5_20"] = safe_divide(
        result["turnover_ma5"], result["turnover_ma20"]
    )

    return result


def calculate_all_volume_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all volume-based factors and merge."""
    vol = calculate_volume_factors(df)
    tur = calculate_turnover_factors(df)
    return vol.merge(tur, on=["stock_code", "trade_date"], how="left")
