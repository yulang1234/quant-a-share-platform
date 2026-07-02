"""
Momentum factor calculations (e.g. N-day return, RSI).

V0.1: skeleton only.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import BaseFactor


class MomentumFactor(BaseFactor):
    """N-day cumulative return as a momentum signal.

    TODO(V0.7): implement configurable windows (5, 20, 60 days).
    """

    name = "momentum_20d"
    category = "momentum"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError("MomentumFactor is a V0.7 feature.")
