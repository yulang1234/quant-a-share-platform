"""
Rank calculator — read factor data, standardize & rank, save results.

V0.8: read stock_daily_factors → rank → write stock_factor_rank.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.factor_rank.factor_config import get_factor_direction
from src.factor_rank.ranker import apply_factor_direction, rank_cross_section
from src.factor_rank.standardizer import standardize_cross_section
from src.storage.duckdb_repo import (
    fetch_daily_factors,
    query_df,
    upsert_factor_rankings,
)

logger = logging.getLogger(__name__)


def get_factor_source_data(
    factor_names: list[str] | None = None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Read factor data from stock_daily_factors."""
    if limit is not None and limit <= 0:
        return pd.DataFrame()
    return fetch_daily_factors(
        stock_code=None, start_date=start_date or trade_date,
        end_date=end_date or trade_date, limit=limit,
    )


def calculate_factor_rankings(
    factor_df: pd.DataFrame,
    factor_names: list[str] | None = None,
    universe_name: str = "core_500",
) -> pd.DataFrame:
    """Standardize and rank factor values."""
    if factor_df is None or factor_df.empty:
        return pd.DataFrame()

    # Determine which factor columns are available
    available = [c for c in factor_df.columns if c not in ("stock_code", "trade_date", "factor_date", "source_adj", "created_at", "updated_at")]
    if factor_names:
        available = [f for f in factor_names if f in available]
    if not available:
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    for fn in available:
        direction = get_factor_direction(fn)
        std = standardize_cross_section(factor_df, fn)
        if std.empty:
            continue
        std = apply_factor_direction(std, direction)
        std = rank_cross_section(std)
        std["universe_name"] = universe_name
        std["rank_method"] = "zscore"
        parts.append(std)

    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def save_factor_rankings(rank_df: pd.DataFrame) -> int:
    """Write rankings to stock_factor_rank (upsert)."""
    if rank_df is None or rank_df.empty:
        return 0
    return upsert_factor_rankings(rank_df)


def run_factor_ranking(
    pool_name: str = "core_500",
    factor_name: str | None = None,
    trade_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Full pipeline: read factors → rank → save."""
    factor_names = [factor_name] if factor_name else None
    source = get_factor_source_data(
        factor_names=None, trade_date=trade_date,
        start_date=start_date, end_date=end_date, limit=limit,
    )
    source_rows = len(source)

    if source.empty:
        return {
            "source_rows": 0, "factor_count": 0,
            "rank_rows": 0, "written_rows": 0,
            "status": "skipped (no factor data)",
        }

    avail = [c for c in source.columns if c not in ("stock_code", "trade_date", "factor_date", "source_adj", "created_at", "updated_at")]
    if factor_name:
        avail = [f for f in avail if f == factor_name]

    rank_df = calculate_factor_rankings(source, avail)
    rank_rows = len(rank_df)
    written = save_factor_rankings(rank_df)

    return {
        "source_rows": source_rows,
        "factor_count": len(avail),
        "rank_rows": rank_rows,
        "written_rows": written,
        "status": "success",
    }
