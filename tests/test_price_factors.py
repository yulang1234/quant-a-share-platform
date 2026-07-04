"""Tests for src/factors/price_factors.py"""
import numpy as np
import pandas as pd
from src.factors.price_factors import calculate_all_price_factors, calculate_return_factors, calculate_moving_average_factors, calculate_price_position_factors


def _make_df(n: int = 70) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({"stock_code": "000001", "trade_date": dates, "close": range(100, 100 + n), "open": range(99, 99 + n), "high": range(101, 101 + n), "low": range(98, 98 + n), "volume": [1000] * n, "amount": [1e6] * n})


class TestReturnFactors:
    def test_return_1d(self) -> None:
        df = _make_df(5)
        r = calculate_return_factors(df)
        assert not np.isnan(r["return_1d"].iloc[1])
        assert np.isnan(r["return_1d"].iloc[0])

    def test_does_not_cross_stocks(self) -> None:
        df1 = _make_df(5)
        df1["stock_code"] = "000001"
        df2 = _make_df(5)
        df2["stock_code"] = "000002"
        df2["close"] += 50
        combined = pd.concat([df1, df2])
        r = calculate_return_factors(combined)
        # last of 000001 should not look at first of 000002
        idx_001 = r[r["stock_code"] == "000001"].index[-1]
        assert np.isnan(r.loc[idx_001, "return_1d"]) or r.loc[idx_001, "return_1d"] != 0


class TestMAFactors:
    def test_ma5(self) -> None:
        df = _make_df(20)
        r = calculate_moving_average_factors(df)
        assert "ma5" in r.columns
        assert "close_ma5_ratio" in r.columns
        assert np.isnan(r["ma5"].iloc[0])  # first 4 NaN

    def test_ma20_ratio(self) -> None:
        df = _make_df(30)
        r = calculate_moving_average_factors(df)
        assert not np.isnan(r["close_ma20_ratio"].iloc[25])


class TestPricePosition:
    def test_no_divide_by_zero(self) -> None:
        df = _make_df(30)
        # Force high==low for one day
        df.loc[25, "high"] = df.loc[25, "low"]
        r = calculate_price_position_factors(df)
        assert "price_position_20d" in r.columns

    def test_price_position_range(self) -> None:
        df = _make_df(60)
        r = calculate_all_price_factors(df)
        vals = r["price_position_20d"].dropna()
        assert (vals >= 0).all() or len(vals) == 0
