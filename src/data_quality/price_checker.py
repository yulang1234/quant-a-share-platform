"""
Price sanity checker — detect abnormal OHLC values.

V0.1: skeleton only.
"""

from __future__ import annotations


def check_price_anomalies(stock_code: str) -> list[dict]:
    """Flag rows where price fields violate business rules (e.g. high < low).

    TODO(V0.5): implement rules: H>=L, C>=L, C<=H, volume>=0, etc.

    Returns
    -------
    list[dict]
    """
    raise NotImplementedError("Price checking is a V0.5 feature.")
