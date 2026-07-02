"""
Price-based factor calculations (e.g. log-return, MA cross).

V0.1: skeleton only.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import BaseFactor


class LogReturnFactor(BaseFactor):
    """Daily log-return factor: log(close / close.shift(1)).

    TODO(V0.7): implement computation on daily_qfq data.
    """

    name = "log_return"
    category = "price"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError("LogReturnFactor is a V0.7 feature.")
