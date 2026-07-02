"""
Base factor interface — all factor calculators inherit from this.

V0.1: abstract skeleton.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseFactor(ABC):
    """Abstract factor calculator.

    Subclasses implement ``compute()`` which receives a daily DataFrame and
    returns a Series of factor values indexed by (stock_code, trade_date).

    TODO(V0.7): add factor metadata (name, category, description).
    """

    name: str = "base_factor"
    category: str = "uncategorised"

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute the factor values.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain at least: stock_code, trade_date, close, volume, …

        Returns
        -------
        pd.Series
            Factor values with a ``pd.MultiIndex`` of (stock_code, trade_date).
        """
        ...
