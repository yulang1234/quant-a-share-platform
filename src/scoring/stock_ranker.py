"""
Stock ranker — aggregate standardised factor scores into a composite ranking.

V0.1: skeleton only.
"""

from __future__ import annotations


def compute_composite_score(
    factor_scores: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    """Weighted sum of standardised factor scores for one stock on one date.

    TODO(V1.3): implement.

    Parameters
    ----------
    factor_scores : dict[str, float]
        ``{factor_name: standardised_score}``.
    weights : dict[str, float] | None
        Per-factor weight.  Equal weighting if ``None``.

    Returns
    -------
    float
    """
    raise NotImplementedError("Composite scoring is a V1.3 feature.")


def rank_stocks(
    scores: dict[str, float],
) -> list[tuple[str, float, int]]:
    """Sort stocks by composite score descending and assign ranks.

    TODO(V1.3): implement.

    Parameters
    ----------
    scores : dict[str, float]
        ``{stock_code: composite_score}``.

    Returns
    -------
    list[tuple[str, float, int]]
        ``(stock_code, score, rank)`` sorted by rank ascending.
    """
    raise NotImplementedError("Stock ranking is a V1.3 feature.")
