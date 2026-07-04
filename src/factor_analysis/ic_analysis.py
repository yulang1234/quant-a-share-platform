"""
IC analysis — Pearson IC and Spearman Rank IC per cross-section.

V0.9: direction_value vs forward_return within each trade_date.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.storage.duckdb_repo import upsert_ic_report


def calculate_daily_ic(
    rank_df: pd.DataFrame,
    forward_df: pd.DataFrame,
    factor_name: str,
    forward_days: int = 5,
    universe_name: str = "core_500",
) -> pd.DataFrame:
    """Calculate daily IC and Rank IC.

    Merges rank data with forward returns on (stock_code, trade_date),
    then computes Pearson IC and Spearman Rank IC per trade_date.

    Parameters
    ----------
    rank_df : pd.DataFrame
        From stock_factor_rank; must have stock_code, trade_date, factor_name, direction_value.
    forward_df : pd.DataFrame
        From factor_forward_returns; must have stock_code, trade_date, forward_return.
    factor_name : str
    forward_days : int
    universe_name : str

    Returns
    -------
    pd.DataFrame
        Columns: factor_name, trade_date, forward_days, ic, rank_ic, sample_count, universe_name.
    """
    if rank_df is None or rank_df.empty or forward_df is None or forward_df.empty:
        return pd.DataFrame(columns=["factor_name", "trade_date", "forward_days", "ic", "rank_ic", "sample_count", "universe_name"])

    # Filter rank data to this factor
    r = rank_df[rank_df["factor_name"] == factor_name].copy()
    if r.empty:
        return pd.DataFrame(columns=["factor_name", "trade_date", "forward_days", "ic", "rank_ic", "sample_count", "universe_name"])

    r["stock_code"] = r["stock_code"].astype(str).str.zfill(6)
    f = forward_df[["stock_code", "trade_date", "forward_return"]].copy()
    f["stock_code"] = f["stock_code"].astype(str).str.zfill(6)

    merged = r.merge(f, on=["stock_code", "trade_date"], how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["factor_name", "trade_date", "forward_days", "ic", "rank_ic", "sample_count", "universe_name"])

    # Drop NaN in direction_value or forward_return
    merged = merged.dropna(subset=["direction_value", "forward_return"])
    if merged.empty:
        return pd.DataFrame(columns=["factor_name", "trade_date", "forward_days", "ic", "rank_ic", "sample_count", "universe_name"])

    results: list[dict] = []
    for td, grp in merged.groupby("trade_date"):
        cnt = len(grp)
        ic_val = float("nan")
        ric_val = float("nan")
        if cnt >= 3:
            ic_val = grp["direction_value"].corr(grp["forward_return"], method="pearson")
            # Rank IC via pandas rank-based correlation (no scipy needed)
            try:
                ric_val = grp["direction_value"].corr(grp["forward_return"], method="spearman")
            except Exception:
                # Fallback: pearson on ranks
                ric_val = grp["direction_value"].rank().corr(grp["forward_return"].rank(), method="pearson")
        results.append({
            "factor_name": factor_name,
            "trade_date": td,
            "forward_days": forward_days,
            "ic": ic_val if not pd.isna(ic_val) else None,
            "rank_ic": ric_val if not pd.isna(ric_val) else None,
            "sample_count": cnt,
            "universe_name": universe_name,
        })

    result_df = pd.DataFrame(results)
    result_df["ic"] = pd.to_numeric(result_df["ic"], errors="coerce")
    result_df["rank_ic"] = pd.to_numeric(result_df["rank_ic"], errors="coerce")
    return result_df


def save_ic_report(ic_df: pd.DataFrame) -> int:
    return upsert_ic_report(ic_df)
