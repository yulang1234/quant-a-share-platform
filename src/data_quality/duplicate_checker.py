"""
Duplicate-checker — detect duplicate rows in daily data.

V0.1: skeleton only.
"""

from __future__ import annotations


def check_duplicates(stock_code: str) -> list[dict]:
    """Find duplicate (stock_code, trade_date) rows in daily tables.

    TODO(V0.5): implement SQL GROUP BY / COUNT check.

    Returns
    -------
    list[dict]
        Each dict describes one duplicate issue.
    """
    raise NotImplementedError("Duplicate checking is a V0.5 feature.")
