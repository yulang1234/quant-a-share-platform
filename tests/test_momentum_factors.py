"""Tests for src/factors/momentum_factors.py"""
import numpy as np
import pandas as pd
from src.factors.momentum_factors import calculate_momentum_factors


def _df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame({"stock_code": "000001", "trade_date": pd.date_range("2026-01-01", periods=n, freq="B"), "close": range(100, 100 + n)})


class TestMomentumFactors:
    def test_momentum_5d_nan_at_start(self) -> None:
        df = _df(10)
        r = calculate_momentum_factors(df)
        assert np.isnan(r["momentum_5d"].iloc[0])

    def test_momentum_5d_value(self) -> None:
        df = _df(10)
        r = calculate_momentum_factors(df)
        # 6th row (index 5): close=105 / close.shift(5)=100 - 1 = 0.05
        assert abs(r["momentum_5d"].iloc[5] - 0.05) < 0.001

    def test_no_cross_stock(self) -> None:
        df1 = _df(8); df1["stock_code"] = "000001"
        df2 = _df(8); df2["stock_code"] = "000002"; df2["close"] += 50
        combined = pd.concat([df1, df2])
        r = calculate_momentum_factors(combined)
        # first row of 000002 should be NaN (not enough prior rows within group)
        idx_002_first = r[r["stock_code"] == "000002"].index[0]
        assert np.isnan(r.loc[idx_002_first, "momentum_5d"])
