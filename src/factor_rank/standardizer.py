"""
Factor standardizer — winsorize then z-score per cross-section.

V0.8: pragmatic functional style.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_series(
    series: pd.Series, lower_quantile: float = 0.01, upper_quantile: float = 0.99,
) -> pd.Series:
    """Clip *series* to [lower_quantile, upper_quantile] bounds.

    NaN values are preserved.  Empty or all-NaN series are returned as-is.
    """
    if series.dropna().empty:
        return series.copy()
    lo = series.quantile(lower_quantile)
    hi = series.quantile(upper_quantile)
    return series.clip(lower=lo, upper=hi)


def zscore_series(series: pd.Series) -> pd.Series:
    """Z-score standardize *series*: (x - mean) / std.

    NaN values are ignored in mean/std.  If std == 0, returns 0 for all
    non-NaN values (constant series).
    """
    valid = series.dropna()
    if len(valid) == 0:
        return series.copy()
    mean = valid.mean()
    std = valid.std(ddof=0)
    if std == 0 or np.isnan(std):
        result = series.copy()
        result[result.notna()] = 0.0
        return result
    return (series - mean) / std


def standardize_cross_section(
    df: pd.DataFrame, factor_name: str,
) -> pd.DataFrame:
    """Standardize *factor_name* within each trade_date cross-section.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: stock_code, trade_date, and *factor_name* column.
    factor_name : str

    Returns
    -------
    pd.DataFrame
        Columns: stock_code, trade_date, factor_name, raw_value,
        clipped_value, zscore_value.
    """
    if df is None or df.empty or factor_name not in df.columns:
        return pd.DataFrame(columns=[
            "stock_code", "trade_date", "factor_name",
            "raw_value", "clipped_value", "zscore_value",
        ])

    result = df[["stock_code", "trade_date"]].copy()
    result["factor_name"] = factor_name
    result["raw_value"] = df[factor_name]

    parts: list[pd.DataFrame] = []
    for dt, grp in result.groupby("trade_date"):
        g = grp.copy()
        raw = g["raw_value"]
        g["clipped_value"] = winsorize_series(raw)
        g["zscore_value"] = zscore_series(g["clipped_value"])
        parts.append(g)

    if not parts:
        return result
    result = pd.concat(parts, ignore_index=True)
    if "stock_code" in result.columns:
        result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    return result
