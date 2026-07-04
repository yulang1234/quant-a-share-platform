"""Tests for src/factors/volatility_factors.py"""
import numpy as np
import pandas as pd
from src.factors.volatility_factors import calculate_volatility_factors


def _df(n: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    closes = [100 + i * 0.5 + (i % 3) * 2 for i in range(n)]
    return pd.DataFrame({"stock_code": "000001", "trade_date": dates, "close": closes})


class TestVolatilityFactors:
    def test_volatility_5d_nan_at_start(self) -> None:
        df = _df(20)
        r = calculate_volatility_factors(df)
        assert np.isnan(r["volatility_5d"].iloc[0])

    def test_volatility_5d_non_negative(self) -> None:
        df = _df(30)
        r = calculate_volatility_factors(df)
        vals = r["volatility_5d"].dropna()
        assert (vals >= 0).all()

    def test_no_cross_stock(self) -> None:
        df1 = _df(10); df1["stock_code"] = "000001"
        df2 = _df(10); df2["stock_code"] = "000002"
        combined = pd.concat([df1, df2])
        r = calculate_volatility_factors(combined)
        # first row of 000002 should be NaN
        idx_002_first = r[r["stock_code"] == "000002"].index[0]
        assert np.isnan(r.loc[idx_002_first, "volatility_5d"])
