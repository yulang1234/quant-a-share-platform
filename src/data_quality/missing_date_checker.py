"""
Missing-date checker — find gaps in daily data for each stock.

V0.1: skeleton only.
"""

from __future__ import annotations


def check_missing_dates(stock_code: str) -> list[dict]:
    """Identify trade-date gaps in a stock's daily series.

    TODO(V0.5): compare actual dates against a trading-calendar reference.

    Returns
    -------
    list[dict]
        Date-range descriptions for each gap found.
    """
    raise NotImplementedError("Missing-date checking is a V0.5 feature.")
