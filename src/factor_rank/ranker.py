"""
Factor ranker — apply direction then rank within cross-section.

V0.8: pragmatic functional style.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def apply_factor_direction(
    df: pd.DataFrame, factor_direction: str,
) -> pd.DataFrame:
    """Add ``direction_value`` column based on *factor_direction*.

    - positive: direction_value = zscore_value
    - negative: direction_value = -zscore_value
    - neutral:  direction_value = zscore_value
    """
    if factor_direction not in ("positive", "negative", "neutral"):
        raise ValueError(
            f"factor_direction must be positive/negative/neutral, got '{factor_direction}'"
        )
    result = df.copy()
    if factor_direction == "negative":
        result["direction_value"] = -result["zscore_value"]
    else:
        result["direction_value"] = result["zscore_value"]
    result["factor_direction"] = factor_direction
    return result


def rank_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``rank_value`` and ``percentile_rank`` per (trade_date, factor_name).

    Higher direction_value → better rank (rank_value=1 is best).
    percentile_rank ∈ [0, 1], higher is better.
    NaN direction_values get NaN ranks.
    """
    result = df.copy()
    result["rank_value"] = np.nan
    result["percentile_rank"] = np.nan

    parts: list[pd.DataFrame] = []
    for (dt, fn), grp in result.groupby(["trade_date", "factor_name"]):
        g = grp.copy()
        valid = g["direction_value"].notna()
        if valid.sum() > 0:
            g.loc[valid, "rank_value"] = (
                g.loc[valid, "direction_value"].rank(ascending=False, method="min")
            )
            g.loc[valid, "percentile_rank"] = (
                g.loc[valid, "direction_value"].rank(pct=True, ascending=True)
            )
        parts.append(g)

    if not parts:
        return result
    result = pd.concat(parts, ignore_index=True)
    if "rank_value" in result.columns:
        result["rank_value"] = result["rank_value"].astype("float64")
    return result.reset_index(drop=True)
