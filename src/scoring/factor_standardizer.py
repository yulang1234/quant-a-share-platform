"""
Factor standardisation — normalise raw factor values to comparable scores.

Methods include Z-score, rank-IC, min-max, and neutralisation (e.g. against
industry or market-cap buckets).

V0.1: skeleton only.
"""

from __future__ import annotations


def zscore_standardize(factor_values: list[float]) -> list[float]:
    """Apply Z-score normalisation (mean=0, std=1).

    TODO(V0.8): implement.

    Parameters
    ----------
    factor_values : list[float]
        Raw factor values for one date.

    Returns
    -------
    list[float]
    """
    raise NotImplementedError("Z-score standardisation is a V0.8 feature.")


def rank_ic(factor_values: list[float], forward_returns: list[float]) -> float:
    """Compute rank IC (Spearman correlation) between factor and forward return.

    TODO(V0.9): implement.

    Returns
    -------
    float
    """
    raise NotImplementedError("Rank IC is a V0.9 feature.")
