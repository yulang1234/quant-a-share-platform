"""Tests for src/factor_rank/ranker.py"""
import numpy as np
import pandas as pd
import pytest
from src.factor_rank.ranker import apply_factor_direction, rank_cross_section


class TestApplyDirection:
    def test_positive(self) -> None:
        df = pd.DataFrame({"zscore_value": [0.5]})
        r = apply_factor_direction(df, "positive")
        assert r["direction_value"].iloc[0] == 0.5

    def test_negative_reverses(self) -> None:
        df = pd.DataFrame({"zscore_value": [0.5]})
        r = apply_factor_direction(df, "negative")
        assert r["direction_value"].iloc[0] == -0.5

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            apply_factor_direction(pd.DataFrame({"zscore_value": [1]}), "invalid")


class TestRankCrossSection:
    def test_best_gets_rank_1(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000002", "000003"],
            "trade_date": pd.to_datetime(["2026-01-02"] * 3),
            "factor_name": ["ret20"] * 3,
            "direction_value": [0.1, 0.3, 0.2],
        })
        r = rank_cross_section(df)
        best = r[r["direction_value"] == 0.3].iloc[0]
        assert best["rank_value"] == 1

    def test_nan_excluded(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000002"],
            "trade_date": pd.to_datetime(["2026-01-02"] * 2),
            "factor_name": ["ret20"] * 2,
            "direction_value": [0.1, np.nan],
        })
        r = rank_cross_section(df)
        assert r["rank_value"].iloc[0] == 1
        assert pd.isna(r["rank_value"].iloc[1])

    def test_no_cross_date(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-03"]),
            "factor_name": ["ret20", "ret20"],
            "direction_value": [0.5, 0.5],
        })
        r = rank_cross_section(df)
        assert (r["rank_value"] == 1).all()
