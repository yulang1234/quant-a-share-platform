"""
Single-factor TopK stock selection.

V1.0: select top_k stocks by percentile_rank within each trade_date.
"""

from __future__ import annotations

import pandas as pd


def select_topk_single_factor(
    rank_df: pd.DataFrame,
    factor_name: str,
    trade_date: str | None = None,
    top_k: int = 20,
    universe_name: str = "core_500",
) -> pd.DataFrame:
    """Select top_k stocks by percentile_rank for a single factor.

    Parameters
    ----------
    rank_df : pd.DataFrame
        From stock_factor_rank; must have stock_code, trade_date, factor_name, percentile_rank.
    factor_name : str
    trade_date : str, optional
        Filter to a single date.
    top_k : int
    universe_name : str

    Returns
    -------
    pd.DataFrame
        Columns: strategy_name, trade_date, stock_code, rank_in_strategy,
        composite_score, factor_count, selected_reason.
    """
    if rank_df is None or rank_df.empty:
        return pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])

    df = rank_df[rank_df["factor_name"] == factor_name].copy()
    if df.empty:
        return pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])

    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)

    if trade_date:
        df = df[df["trade_date"] == pd.Timestamp(trade_date)]

    if df.empty:
        return pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])

    # Drop NaN percentile_rank
    df = df.dropna(subset=["percentile_rank"])

    results: list[dict] = []
    for td, grp in df.groupby("trade_date"):
        grp = grp.sort_values("percentile_rank", ascending=False).head(top_k)
        for i, (_, row) in enumerate(grp.iterrows()):
            results.append({
                "strategy_name": "",
                "trade_date": td,
                "stock_code": row["stock_code"],
                "rank_in_strategy": i + 1,
                "composite_score": row["percentile_rank"],
                "factor_count": 1,
                "selected_reason": f"factor={factor_name}",
            })

    if not results:
        return pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])

    return pd.DataFrame(results)
