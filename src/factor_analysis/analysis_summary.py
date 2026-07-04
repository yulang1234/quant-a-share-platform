"""
Analysis summary — aggregate IC and group returns into a per-factor summary.

V0.9: IC/IR/positive ratio/top-bottom spread.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.storage.duckdb_repo import upsert_analysis_summary


def summarize_factor_analysis(
    ic_df: pd.DataFrame,
    group_df: pd.DataFrame,
    factor_name: str,
    forward_days: int = 5,
    start_date: str | None = None,
    end_date: str | None = None,
    universe_name: str = "core_500",
) -> pd.DataFrame:
    """Produce a one-row summary DataFrame for a single factor.

    *start_date* / *end_date* are guaranteed non-NULL: if the caller does
    not provide them, they are inferred from the trade_date range in
    *ic_df* or *group_df*.  If no dates are available at all, a sentinel
    ``1900-01-01`` is used so the primary key never fails.
    """
    # ── Infer date bounds ────────────────────────────────────────────
    if not start_date or not end_date:
        dates: list = []
        if ic_df is not None and not ic_df.empty and "trade_date" in ic_df.columns:
            dates.extend(pd.to_datetime(ic_df["trade_date"]).dropna().tolist())
        if group_df is not None and not group_df.empty and "trade_date" in group_df.columns:
            dates.extend(pd.to_datetime(group_df["trade_date"]).dropna().tolist())
        if dates:
            if not start_date:
                start_date = min(dates).strftime("%Y-%m-%d")
            if not end_date:
                end_date = max(dates).strftime("%Y-%m-%d")
        else:
            start_date = start_date or "1900-01-01"
            end_date = end_date or "1900-01-01"

    row: dict = {
        "factor_name": factor_name,
        "forward_days": forward_days,
        "start_date": start_date,
        "end_date": end_date,
        "universe_name": universe_name,
        "avg_ic": None, "avg_rank_ic": None, "ic_std": None, "rank_ic_std": None,
        "ic_ir": None, "rank_ic_ir": None,
        "positive_ic_ratio": None, "positive_rank_ic_ratio": None,
        "avg_top_group_return": None, "avg_bottom_group_return": None,
        "avg_group_spread": None, "trade_date_count": 0,
    }

    if ic_df is not None and not ic_df.empty:
        ic = ic_df["ic"].dropna() if "ic" in ic_df.columns else pd.Series(dtype=float)
        ric = ic_df["rank_ic"].dropna() if "rank_ic" in ic_df.columns else pd.Series(dtype=float)
        row["trade_date_count"] = len(ic_df)
        if len(ic) > 0:
            row["avg_ic"] = float(ic.mean())
            row["ic_std"] = float(ic.std(ddof=0)) if len(ic) > 1 else 0.0
            row["ic_ir"] = row["avg_ic"] / row["ic_std"] if row["ic_std"] and row["ic_std"] != 0 else None
            row["positive_ic_ratio"] = float((ic > 0).mean())
        if len(ric) > 0:
            row["avg_rank_ic"] = float(ric.mean())
            row["rank_ic_std"] = float(ric.std(ddof=0)) if len(ric) > 1 else 0.0
            row["rank_ic_ir"] = row["avg_rank_ic"] / row["rank_ic_std"] if row["rank_ic_std"] and row["rank_ic_std"] != 0 else None
            row["positive_rank_ic_ratio"] = float((ric > 0).mean())

    if group_df is not None and not group_df.empty and "group_id" in group_df.columns:
        gids = group_df["group_id"].dropna().unique()
        if len(gids) >= 2:
            top_gid = int(gids.max())
            bot_gid = int(gids.min())
            top_avg = group_df[group_df["group_id"] == top_gid]["avg_forward_return"].mean()
            bot_avg = group_df[group_df["group_id"] == bot_gid]["avg_forward_return"].mean()
            row["avg_top_group_return"] = float(top_avg) if not pd.isna(top_avg) else None
            row["avg_bottom_group_return"] = float(bot_avg) if not pd.isna(bot_avg) else None
            if row["avg_top_group_return"] is not None and row["avg_bottom_group_return"] is not None:
                row["avg_group_spread"] = row["avg_top_group_return"] - row["avg_bottom_group_return"]

    return pd.DataFrame([row])


def save_analysis_summary(summary_df: pd.DataFrame) -> int:
    return upsert_analysis_summary(summary_df)
