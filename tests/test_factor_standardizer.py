"""Tests for src/factor_rank/standardizer.py"""
import numpy as np
import pandas as pd
from src.factor_rank.standardizer import standardize_cross_section, winsorize_series, zscore_series


class TestWinsorize:
    def test_clips_outliers(self) -> None:
        s = pd.Series([1, 2, 3, 100])
        r = winsorize_series(s, 0.25, 0.75)
        assert r.max() < 100

    def test_preserves_nan(self) -> None:
        s = pd.Series([1, np.nan, 3])
        r = winsorize_series(s)
        assert np.isnan(r.iloc[1])

    def test_all_nan_ok(self) -> None:
        s = pd.Series([np.nan, np.nan])
        r = winsorize_series(s)
        assert r.isna().all()


class TestZscore:
    def test_mean_zero(self) -> None:
        s = pd.Series([1, 2, 3, 4, 5], dtype=float)
        r = zscore_series(s)
        assert abs(r.mean()) < 1e-9

    def test_constant_returns_zero(self) -> None:
        s = pd.Series([5.0, 5.0, 5.0])
        r = zscore_series(s)
        assert (r == 0).all()

    def test_all_nan_ok(self) -> None:
        s = pd.Series([np.nan, np.nan])
        r = zscore_series(s)
        assert r.isna().all()


class TestStandardizeCrossSection:
    def test_output_columns(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000002", "000001", "000002"],
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-03", "2026-01-03"]),
            "ret20": [0.01, 0.02, -0.01, 0.03],
        })
        r = standardize_cross_section(df, "ret20")
        assert "raw_value" in r.columns
        assert "clipped_value" in r.columns
        assert "zscore_value" in r.columns

    def test_not_cross_date(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-03"]),
            "ret20": [0.10, 0.10],
        })
        r = standardize_cross_section(df, "ret20")
        # both zscore should be 0 (each date has only 1 stock)
        assert (r["zscore_value"] == 0).all()

    def test_empty_df(self) -> None:
        r = standardize_cross_section(pd.DataFrame(), "x")
        assert r.empty
