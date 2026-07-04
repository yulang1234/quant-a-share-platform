"""
Group analysis — split stocks into N groups by direction_value, compute group returns.

V0.9: higher direction_value → higher group_id → better.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.storage.duckdb_repo import upsert_group_return_report


def assign_factor_groups(df: pd.DataFrame, group_count: int = 5) -> pd.DataFrame:
    """Assign group_id per (trade_date, factor_name) based on direction_value.

    group_id ∈ [1, group_count], higher = better factor value.
    NaN values get NaN group_id.
    """
    if df is None or df.empty or "direction_value" not in df.columns:
        return df

    result = df.copy()
    result["group_id"] = np.nan

    for (td, fn), grp in result.groupby(["trade_date", "factor_name"]):
        valid = grp["direction_value"].notna()
        if valid.sum() < group_count:
            continue
        try:
            result.loc[valid[valid].index, "group_id"] = (
                pd.qcut(grp.loc[valid, "direction_value"], group_count, labels=False, duplicates="drop") + 1
            )
        except Exception:
            continue

    result["group_count"] = group_count
    return result


def calculate_group_returns(
    rank_df: pd.DataFrame,
    forward_df: pd.DataFrame,
    factor_name: str,
    forward_days: int = 5,
    group_count: int = 5,
    universe_name: str = "core_500",
) -> pd.DataFrame:
    """Calculate average/median forward return per group per trade_date."""
    if rank_df is None or rank_df.empty or forward_df is None or forward_df.empty:
        return pd.DataFrame(columns=[
            "factor_name", "trade_date", "forward_days", "group_id", "group_count",
            "avg_forward_return", "median_forward_return", "stock_count", "universe_name",
        ])

    r = rank_df[rank_df["factor_name"] == factor_name].copy()
    if r.empty:
        return pd.DataFrame(columns=[
            "factor_name", "trade_date", "forward_days", "group_id", "group_count",
            "avg_forward_return", "median_forward_return", "stock_count", "universe_name",
        ])

    r["stock_code"] = r["stock_code"].astype(str).str.zfill(6)
    f = forward_df[["stock_code", "trade_date", "forward_return"]].copy()
    f["stock_code"] = f["stock_code"].astype(str).str.zfill(6)

    merged = r.merge(f, on=["stock_code", "trade_date"], how="inner")
    if merged.empty:
        return pd.DataFrame(columns=[
            "factor_name", "trade_date", "forward_days", "group_id", "group_count",
            "avg_forward_return", "median_forward_return", "stock_count", "universe_name",
        ])

    grouped = assign_factor_groups(merged, group_count)
    grouped = grouped.dropna(subset=["group_id", "forward_return"])
    if grouped.empty:
        return pd.DataFrame(columns=[
            "factor_name", "trade_date", "forward_days", "group_id", "group_count",
            "avg_forward_return", "median_forward_return", "stock_count", "universe_name",
        ])

    agg = grouped.groupby(["trade_date", "group_id"]).agg(
        avg_forward_return=("forward_return", "mean"),
        median_forward_return=("forward_return", "median"),
        stock_count=("forward_return", "count"),
    ).reset_index()

    agg["factor_name"] = factor_name
    agg["forward_days"] = forward_days
    agg["group_count"] = group_count
    agg["universe_name"] = universe_name
    return agg


def save_group_return_report(group_df: pd.DataFrame) -> int:
    return upsert_group_return_report(group_df)
