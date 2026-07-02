"""
AkShare data client — placeholder for real API integration.

AkShare (https://akshare.akfamily.xyz/) provides free A-share market data.
This module will wrap its most-used endpoints in later versions.

Current status (V0.1): all methods raise ``NotImplementedError``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class AkShareClient:
    """Thin wrapper around akshare functions for A-share market data.

    V0.1 — skeleton only.  Real API calls will be added from V0.3 onward.
    """

    def __init__(self) -> None:
        """Initialize the client.

        TODO(V0.3): set up session-level caching / rate-limiting.
        """
        pass

    def fetch_stock_basic(self) -> pd.DataFrame:
        """Fetch the full A-share stock list.

        Returns
        -------
        pd.DataFrame
            Columns: stock_code, stock_name, industry, listing_date, etc.

        TODO(V0.3): call ``ak.stock_info_a_code_name()`` or similar.
        """
        raise NotImplementedError(
            "fetch_stock_basic will be implemented in V0.3 (historical data init)."
        )

    def fetch_stock_daily_raw(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch unadjusted daily K-line for one stock.

        Parameters
        ----------
        stock_code : str
            6-digit A-stock code, e.g. ``"000001"``.
        start_date : str
            ``"YYYYMMDD"`` or ``"YYYY-MM-DD"``.
        end_date : str
            ``"YYYYMMDD"`` or ``"YYYY-MM-DD"``.

        Returns
        -------
        pd.DataFrame
            Columns: open, high, low, close, pre_close, volume, amount, …

        TODO(V0.3): call ``ak.stock_zh_a_hist(symbol=..., …)`` with ``adjust=""``.
        """
        raise NotImplementedError(
            "fetch_stock_daily_raw will be implemented in V0.3."
        )

    def fetch_stock_daily_qfq(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch forward-adjusted (QFQ) daily K-line for one stock.

        Parameters
        ----------
        stock_code : str
            6-digit A-stock code.
        start_date : str
            ``"YYYYMMDD"`` or ``"YYYY-MM-DD"``.
        end_date : str
            ``"YYYYMMDD"`` or ``"YYYY-MM-DD"``.

        Returns
        -------
        pd.DataFrame
            Columns: open, high, low, close, volume, amount, pct_change, …

        TODO(V0.3): call ``ak.stock_zh_a_hist(symbol=..., …)`` with ``adjust="qfq"``.
        """
        raise NotImplementedError(
            "fetch_stock_daily_qfq will be implemented in V0.3."
        )
