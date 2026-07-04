"""Factor filter by analysis summary. V1.3."""
from __future__ import annotations
import pandas as pd
from src.storage.duckdb_repo import fetch_analysis_summary


def get_factor_analysis_info(factor_names: list[str]) -> pd.DataFrame:
    try:
        return fetch_analysis_summary(limit=1000)
    except Exception:
        return pd.DataFrame()


def filter_factors_by_analysis(
    factor_names: list[str],
    min_avg_rank_ic: float | None = None,
    min_positive_rank_ic_ratio: float | None = None,
    min_avg_group_spread: float | None = None,
) -> list[str]:
    summary = get_factor_analysis_info(factor_names)
    if summary.empty: return list(factor_names)

    result = list(factor_names)
    for fn in list(result):
        row = summary[summary["factor_name"] == fn]
        if row.empty: continue
        r = row.iloc[0]
        if min_avg_rank_ic is not None and r.get("avg_rank_ic") is not None and r["avg_rank_ic"] < min_avg_rank_ic:
            result.remove(fn); continue
        if min_positive_rank_ic_ratio is not None and r.get("positive_rank_ic_ratio") is not None and r["positive_rank_ic_ratio"] < min_positive_rank_ic_ratio:
            result.remove(fn); continue
        if min_avg_group_spread is not None and r.get("avg_group_spread") is not None and r["avg_group_spread"] < min_avg_group_spread:
            result.remove(fn)
    return result
