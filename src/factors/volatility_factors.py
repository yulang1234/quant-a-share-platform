"""
Volatility factor calculations (e.g. std of returns, ATR).

V0.1: skeleton only.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import BaseFactor


class VolatilityFactor(BaseFactor):
    """N-day rolling volatility of daily returns.

    TODO(V0.7): implement configurable windows.
    """

    name = "volatility_20d"
    category = "volatility"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError("VolatilityFactor is a V0.7 feature.")
