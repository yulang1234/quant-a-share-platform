"""
Strategy selector — execute strategies and save results.

V1.0: single / multi factor TopK, with optional effectiveness filtering.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.storage.duckdb_repo import (
    fetch_analysis_summary,
    fetch_factor_rankings,
    upsert_strategy_config,
    upsert_strategy_selection_detail,
    upsert_strategy_selection_result,
)
from src.strategy.multi_factor_strategy import select_topk_multi_factor
from src.strategy.single_factor_strategy import select_topk_single_factor
from src.strategy.strategy_config import get_default_strategy, validate_strategy_config


def get_rank_data(
    factor_names: list[str] | None = None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Read rank data from stock_factor_rank."""
    return fetch_factor_rankings(
        factor_name=factor_names[0] if factor_names and len(factor_names) == 1 else None,
        trade_date=trade_date, start_date=start_date, end_date=end_date, limit=limit,
    )


def filter_factors_by_effectiveness(
    factor_names: list[str],
    min_avg_rank_ic: float | None = None,
    min_positive_rank_ic_ratio: float | None = None,
    min_group_spread: float | None = None,
) -> list[str]:
    """Filter factor names based on V0.9 effectiveness summary."""
    summary = fetch_analysis_summary(limit=1000)
    if summary.empty:
        return factor_names

    for fn in list(factor_names):
        row = summary[summary["factor_name"] == fn]
        if row.empty:
            continue
        r = row.iloc[0]
        if min_avg_rank_ic is not None and r.get("avg_rank_ic", 0) is not None:
            if r["avg_rank_ic"] < min_avg_rank_ic:
                factor_names.remove(fn)
                continue
        if min_positive_rank_ic_ratio is not None and r.get("positive_rank_ic_ratio", 0) is not None:
            if r["positive_rank_ic_ratio"] < min_positive_rank_ic_ratio:
                factor_names.remove(fn)
                continue
        if min_group_spread is not None and r.get("avg_group_spread", 0) is not None:
            if r["avg_group_spread"] < min_group_spread:
                factor_names.remove(fn)
                continue
    return factor_names


def run_strategy(
    config: dict[str, Any],
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    universe_name: str = "core_500",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute a strategy, return (selection_df, detail_df)."""
    validate_strategy_config(config)
    sname = config["strategy_name"]
    stype = config["strategy_type"]
    top_k = config.get("top_k", 20)

    if stype == "single_factor":
        fn = config["factor_name"]
        rank = get_rank_data([fn], trade_date, start_date, end_date, limit)
        sel = select_topk_single_factor(rank, fn, trade_date, top_k, universe_name)
        det = pd.DataFrame(columns=["trade_date", "stock_code", "factor_name", "factor_score", "factor_weight", "weighted_score", "factor_rank_value", "factor_percentile_rank"])
        if not sel.empty:
            sel["strategy_name"] = sname
    else:
        weights = config["factor_weights"]
        if isinstance(weights, str):
            weights = json.loads(weights)
        rank = get_rank_data(list(weights.keys()), trade_date, start_date, end_date, limit)
        sel, det = select_topk_multi_factor(rank, weights, trade_date, top_k, universe_name)
        if not sel.empty:
            sel["strategy_name"] = sname
        if not det.empty:
            det["strategy_name"] = sname
            det["universe_name"] = universe_name

    if not sel.empty:
        sel["universe_name"] = universe_name
    return sel, det


def save_strategy_results(selection_df: pd.DataFrame, detail_df: pd.DataFrame) -> dict[str, int]:
    """Save selection and detail to DuckDB. Returns {written_selection, written_detail}."""
    s = upsert_strategy_selection_result(selection_df) if not selection_df.empty else 0
    d = upsert_strategy_selection_detail(detail_df) if not detail_df.empty else 0
    return {"written_selection_rows": s, "written_detail_rows": d}


def run_and_save_strategy(
    config: dict[str, Any],
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    universe_name: str = "core_500",
    save_config: bool = True,
) -> dict[str, Any]:
    """Full pipeline: run strategy, save results, return summary.

    *save_config* controls whether the strategy config is persisted to
    ``strategy_config``.  Set to ``False`` for adhoc / temporary strategies.
    """
    if save_config:
        cf = pd.DataFrame([{k: v for k, v in config.items() if k != "factor_weights"}])
        if "factor_weights" in config:
            w = config["factor_weights"]
            cf["factor_weights"] = json.dumps(w) if isinstance(w, dict) else str(w)
        upsert_strategy_config(cf)

    sel, det = run_strategy(config, trade_date, start_date, end_date, limit, universe_name)
    written = save_strategy_results(sel, det)

    return {
        "strategy_name": config["strategy_name"],
        "strategy_type": config["strategy_type"],
        "selection_rows": len(sel),
        "detail_rows": len(det),
        "written_selection_rows": written["written_selection_rows"],
        "written_detail_rows": written["written_detail_rows"],
        "status": "success" if len(sel) > 0 else "skipped (no candidates)",
    }
