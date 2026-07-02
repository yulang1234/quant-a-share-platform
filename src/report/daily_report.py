"""
Daily candidate report — generate a human-readable summary of today's picks.

V0.1: skeleton only.
"""

from __future__ import annotations


def generate_daily_report(trade_date: str | None = None) -> str:
    """Produce a markdown report of candidate stocks and key metrics.

    TODO(V1.5): read stock_candidate_daily, scores, and quality report.

    Parameters
    ----------
    trade_date : str, optional
        Date string ``"YYYY-MM-DD"``.  Defaults to the latest available date.

    Returns
    -------
    str
        Markdown report content.
    """
    raise NotImplementedError("Daily report is a V1.5 feature.")
