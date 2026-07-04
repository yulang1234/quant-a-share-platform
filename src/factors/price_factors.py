"""
Price-based factor calculations — return, MA, price position.

V0.7: full implementation.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import safe_divide, validate_factor_input


def _grouped_shift(series: pd.Series, group_col: pd.Series, n: int) -> pd.Series:
    """Shift *series* by *n* within each group defined by *group_col*."""
    return series.groupby(group_col).shift(n)


def calculate_return_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate return_Nd factors: close / close.shift(N) - 1."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date"]].copy()

    for n in (1, 5, 10, 20, 60):
        shifted = _grouped_shift(df["close"], df["stock_code"], n)
        result[f"return_{n}d"] = (df["close"] / shifted) - 1

    return result


def calculate_moving_average_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MA and close/MA ratio factors."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date", "close"]].copy()

    for n in (5, 10, 20, 60, 120):
        ma = df.groupby("stock_code")["close"].transform(
            lambda x: x.rolling(n, min_periods=n).mean()
        )
        result[f"ma{n}"] = ma
        result[f"close_ma{n}_ratio"] = safe_divide(result["close"], ma) - 1

    return result.drop(columns=["close"])


def calculate_price_position_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate high_Nd, low_Nd, price_position_Nd factors."""
    df = validate_factor_input(df)
    result = df[["stock_code", "trade_date", "close"]].copy()

    for col in ("high", "low"):
        if col not in df.columns:
            df[col] = float("nan")

    for n in (20, 60):
        high_n = df.groupby("stock_code")["high"].transform(
            lambda x: x.rolling(n, min_periods=n).max()
        )
        low_n = df.groupby("stock_code")["low"].transform(
            lambda x: x.rolling(n, min_periods=n).min()
        )
        result[f"high_{n}d"] = high_n
        result[f"low_{n}d"] = low_n
        denom = high_n - low_n
        result[f"price_position_{n}d"] = safe_divide(result["close"] - low_n, denom)

    return result.drop(columns=["close"])


def calculate_all_price_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all price-based factors and merge into one DataFrame."""
    ret = calculate_return_factors(df)
    ma = calculate_moving_average_factors(df)
    pos = calculate_price_position_factors(df)

    result = ret.merge(ma, on=["stock_code", "trade_date"], how="left")
    result = result.merge(pos, on=["stock_code", "trade_date"], how="left")
    return result
