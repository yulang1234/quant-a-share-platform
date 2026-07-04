"""
Multi-factor weighted TopK stock selection.

V1.0: composite_score = sum(percentile_rank * normalized_weight)
"""

from __future__ import annotations

import json

import pandas as pd


def normalize_factor_weights(factor_weights: dict[str, float]) -> dict[str, float]:
    """Normalize weights to sum to 1.

    Raises ValueError if any weight is negative or total is zero.
    """
    if not factor_weights:
        raise ValueError("factor_weights is empty")
    for k, v in factor_weights.items():
        if v < 0:
            raise ValueError(f"Negative weight for '{k}': {v}")
    total = sum(factor_weights.values())
    if total == 0:
        raise ValueError("Sum of factor_weights is zero")
    return {k: v / total for k, v in factor_weights.items()}


def calculate_composite_scores(
    rank_df: pd.DataFrame,
    factor_weights: dict[str, float],
    trade_date: str | None = None,
    universe_name: str = "core_500",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate composite scores and per-factor detail.

    Returns (selection_df, detail_df).
    """
    if rank_df is None or rank_df.empty:
        empty_sel = pd.DataFrame(columns=["trade_date", "stock_code", "composite_score", "factor_count", "selected_reason"])
        empty_det = pd.DataFrame(columns=["trade_date", "stock_code", "factor_name", "factor_score", "factor_weight", "weighted_score", "factor_rank_value", "factor_percentile_rank"])
        return empty_sel, empty_det

    weights = normalize_factor_weights(dict(factor_weights))
    factor_names = list(weights.keys())

    df = rank_df[rank_df["factor_name"].isin(factor_names)].copy()
    if df.empty:
        empty_sel = pd.DataFrame(columns=["trade_date", "stock_code", "composite_score", "factor_count", "selected_reason"])
        empty_det = pd.DataFrame(columns=["trade_date", "stock_code", "factor_name", "factor_score", "factor_weight", "weighted_score", "factor_rank_value", "factor_percentile_rank"])
        return empty_sel, empty_det

    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    if trade_date:
        df = df[df["trade_date"] == pd.Timestamp(trade_date)]

    # Build detail
    detail_rows: list[dict] = []
    for _, row in df.iterrows():
        fn = row["factor_name"]
        w = weights.get(fn, 0)
        pr = row.get("percentile_rank")
        if pd.isna(pr):
            continue
        detail_rows.append({
            "trade_date": row["trade_date"],
            "stock_code": row["stock_code"],
            "factor_name": fn,
            "factor_score": pr,
            "factor_weight": w,
            "weighted_score": pr * w,
            "factor_rank_value": row.get("rank_value"),
            "factor_percentile_rank": pr,
        })

    detail_df = pd.DataFrame(detail_rows)
    if detail_df.empty:
        empty_sel = pd.DataFrame(columns=["trade_date", "stock_code", "composite_score", "factor_count", "selected_reason"])
        return empty_sel, detail_df

    # Aggregate to composite
    agg = detail_df.groupby(["trade_date", "stock_code"]).agg(
        composite_score=("weighted_score", "sum"),
        factor_count=("factor_name", "count"),
        selected_reason=("factor_name", lambda x: ",".join(sorted(x))),
    ).reset_index()

    return agg, detail_df


def select_topk_multi_factor(
    rank_df: pd.DataFrame,
    factor_weights: dict[str, float],
    trade_date: str | None = None,
    top_k: int = 20,
    universe_name: str = "core_500",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select top_k stocks by composite score.

    Returns (selection_df, detail_df).
    """
    if isinstance(factor_weights, str):
        factor_weights = json.loads(factor_weights)

    agg, detail_df = calculate_composite_scores(rank_df, factor_weights, trade_date, universe_name)

    if agg.empty:
        empty_sel = pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])
        return empty_sel, detail_df

    results: list[dict] = []
    for td, grp in agg.groupby("trade_date"):
        grp = grp.sort_values("composite_score", ascending=False).head(top_k)
        for i, (_, row) in enumerate(grp.iterrows()):
            results.append({
                "strategy_name": "",
                "trade_date": td,
                "stock_code": row["stock_code"],
                "rank_in_strategy": i + 1,
                "composite_score": row["composite_score"],
                "factor_count": row["factor_count"],
                "selected_reason": row["selected_reason"],
            })

    sel_df = pd.DataFrame(results) if results else pd.DataFrame(columns=["strategy_name", "trade_date", "stock_code", "rank_in_strategy", "composite_score", "factor_count", "selected_reason"])

    # Filter detail to selected stocks
    if not sel_df.empty and not detail_df.empty:
        selected_keys = set(zip(sel_df["trade_date"], sel_df["stock_code"]))
        detail_df = detail_df[detail_df.apply(lambda r: (r["trade_date"], r["stock_code"]) in selected_keys, axis=1)]

    return sel_df, detail_df
