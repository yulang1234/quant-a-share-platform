"""
Position builder — rebalance dates, equal-weight positions, daily expansion.

V1.1: basic rebalance schedule + equal-weight positions.
"""

from __future__ import annotations

import pandas as pd

from src.storage.duckdb_repo import fetch_strategy_selection_result


def get_strategy_selection_data(
    strategy_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    top_k: int | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    df = fetch_strategy_selection_result(strategy_name=strategy_name, start_date=start_date, end_date=end_date, limit=limit)
    if df.empty:
        return df
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    if "rank_in_strategy" in df.columns and top_k:
        df = df[df["rank_in_strategy"] <= top_k]
    return df.sort_values(["trade_date", "rank_in_strategy"]).reset_index(drop=True)


def get_rebalance_dates(selection_df: pd.DataFrame, frequency: str = "monthly") -> list[pd.Timestamp]:
    if selection_df.empty or "trade_date" not in selection_df.columns:
        return []
    dates = pd.to_datetime(selection_df["trade_date"].dropna().unique())
    dates = sorted(dates)
    if frequency == "daily":
        return dates
    if frequency == "weekly":
        result = []
        for d in dates:
            if not result or d.isocalendar()[1] != result[-1].isocalendar()[1]:
                result.append(d)
        return result
    if frequency == "monthly":
        result = []
        for d in dates:
            if not result or (d.year != result[-1].year or d.month != result[-1].month):
                result.append(d)
        return result
    return dates


def build_equal_weight_positions(
    selection_df: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
    top_k: int = 20,
) -> pd.DataFrame:
    if selection_df.empty or not rebalance_dates:
        return pd.DataFrame(columns=["rebalance_date", "stock_code", "weight", "rank_in_strategy", "composite_score"])

    selection_df["trade_date"] = pd.to_datetime(selection_df["trade_date"])
    rows = []
    for rd in rebalance_dates:
        candidates = selection_df[selection_df["trade_date"] == rd]
        if "rank_in_strategy" in candidates.columns:
            candidates = candidates.sort_values("rank_in_strategy").head(top_k)
        else:
            candidates = candidates.head(top_k)
        if candidates.empty:
            continue
        w = 1.0 / len(candidates)
        for _, r in candidates.iterrows():
            rows.append({
                "rebalance_date": rd,
                "stock_code": str(r["stock_code"]).zfill(6),
                "weight": w,
                "rank_in_strategy": r.get("rank_in_strategy"),
                "composite_score": r.get("composite_score"),
            })
    if not rows:
        return pd.DataFrame(columns=["rebalance_date", "stock_code", "weight", "rank_in_strategy", "composite_score"])
    return pd.DataFrame(rows)


def expand_positions_to_daily(
    position_df: pd.DataFrame,
    price_dates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Expand rebalance-date positions to daily holdings."""
    if position_df.empty or price_dates_df.empty or "trade_date" not in price_dates_df.columns:
        return pd.DataFrame(columns=["rebalance_date", "trade_date", "stock_code", "weight", "rank_in_strategy", "composite_score"])

    all_dates = sorted(pd.to_datetime(price_dates_df["trade_date"].dropna().unique()))
    rd_list = sorted(position_df["rebalance_date"].dropna().unique())
    if not rd_list or not all_dates:
        return pd.DataFrame(columns=["rebalance_date", "trade_date", "stock_code", "weight", "rank_in_strategy", "composite_score"])

    rows = []
    for i, rd in enumerate(rd_list):
        next_rd = rd_list[i + 1] if i + 1 < len(rd_list) else all_dates[-1] + pd.Timedelta(days=1)
        hold_dates = [d for d in all_dates if rd <= d < next_rd]
        pos = position_df[position_df["rebalance_date"] == rd]
        for td in hold_dates:
            for _, r in pos.iterrows():
                rows.append({
                    "rebalance_date": rd,
                    "trade_date": td,
                    "stock_code": r["stock_code"],
                    "weight": r["weight"],
                    "rank_in_strategy": r.get("rank_in_strategy"),
                    "composite_score": r.get("composite_score"),
                })
    if not rows:
        return pd.DataFrame(columns=["rebalance_date", "trade_date", "stock_code", "weight", "rank_in_strategy", "composite_score"])
    return pd.DataFrame(rows)
