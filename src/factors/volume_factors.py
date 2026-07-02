"""
Volume-based factor calculations (e.g. turnover, volume ratio).

V0.1: skeleton only.
"""

from __future__ import annotations

import pandas as pd

from src.factors.base_factor import BaseFactor


class TurnoverFactor(BaseFactor):
    """Turnover-rate factor (raw value from daily data).

    TODO(V0.7): implement.
    """

    name = "turnover"
    category = "volume"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError("TurnoverFactor is a V0.7 feature.")
