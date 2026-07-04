"""Tests for src/factors/volume_factors.py"""
import numpy as np
import pandas as pd
from src.factors.volume_factors import calculate_volume_factors, calculate_turnover_factors


def _df(n: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({"stock_code": "000001", "trade_date": dates, "close": range(100, 100 + n), "volume": [1000 + i * 10 for i in range(n)], "amount": [1e6 + i * 1000 for i in range(n)], "turnover_rate": [0.5 + i * 0.01 for i in range(n)]})


class TestVolumeFactors:
    def test_volume_ma5_nan_start(self) -> None:
        r = calculate_volume_factors(_df(20))
        assert np.isnan(r["volume_ma5"].iloc[0])

    def test_volume_ma5_value(self) -> None:
        r = calculate_volume_factors(_df(10))
        assert not np.isnan(r["volume_ma5"].iloc[5])

    def test_volume_ratio_no_nan(self) -> None:
        r = calculate_volume_factors(_df(40))
        v = r["volume_ratio_5_20"].dropna()
        assert len(v) > 0

    def test_amount_ma20(self) -> None:
        r = calculate_volume_factors(_df(30))
        assert "amount_ma20" in r.columns

    def test_missing_turnover_does_not_crash(self) -> None:
        df = _df(20).drop(columns=["turnover_rate"])
        r = calculate_turnover_factors(df)
        assert r["turnover_ma5"].isna().all()
