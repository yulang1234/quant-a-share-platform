"""
Base factor utilities — validation, division, column helpers.

V0.7: pragmatic functional style, not abstract OOP.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def validate_factor_input(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise factor input DataFrame.

    Returns a sorted copy — never modifies the original.
    """
    if df is None or df.empty:
        raise ValueError("Input DataFrame is empty")
    if "close" not in df.columns:
        raise ValueError("Input DataFrame missing 'close' column")

    result = df.copy()
    if "stock_code" in result.columns:
        result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    if "trade_date" in result.columns:
        result["trade_date"] = pd.to_datetime(result["trade_date"])

    sort_cols = [c for c in ("stock_code", "trade_date") if c in result.columns]
    if sort_cols:
        result = result.sort_values(sort_cols).reset_index(drop=True)
    return result


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Element-wise division: numerator / denominator.

    Returns NaN where denominator is 0, NaN, or inf.
    """
    denominator = denominator.replace([0, np.inf, -np.inf], np.nan)
    return numerator / denominator


def ensure_factor_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Ensure *columns* exist in *df*, filling with NaN where missing."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = np.nan
    return df
