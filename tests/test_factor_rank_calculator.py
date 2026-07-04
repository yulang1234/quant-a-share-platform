"""Tests for src/factor_rank/rank_calculator.py"""
import pandas as pd
from src.factor_rank.rank_calculator import calculate_factor_rankings, run_factor_ranking, save_factor_rankings


class TestCalculate:
    def test_empty_returns_empty(self) -> None:
        r = calculate_factor_rankings(pd.DataFrame())
        assert r.empty

    def test_with_known_factor(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000002", "000003"] * 3,
            "trade_date": pd.to_datetime(["2026-01-02"] * 9),
            "return_20d": [0.01, 0.02, 0.03] * 3,
            "volatility_20d": [0.1, 0.2, 0.3] * 3,
        })
        r = calculate_factor_rankings(df, ["return_20d"])
        assert not r.empty
        assert "rank_value" in r.columns
        assert "percentile_rank" in r.columns
        assert "direction_value" in r.columns
        # only return_20d
        assert (r["factor_name"] == "return_20d").all()


class TestSaveAndRun:
    def test_empty_save(self, fresh_db) -> None:  # noqa: F811
        assert save_factor_rankings(pd.DataFrame()) == 0

    def test_upsert_idempotent(self, fresh_db) -> None:  # noqa: F811
        df = pd.DataFrame({
            "stock_code": ["000001"], "trade_date": [pd.Timestamp("2026-01-02").date()],
            "factor_name": ["return_20d"], "raw_value": [0.01],
            "zscore_value": [0.5], "direction_value": [0.5],
            "rank_value": [1], "percentile_rank": [1.0],
            "factor_direction": ["positive"], "universe_name": ["core_500"],
        })
        n1 = save_factor_rankings(df)
        n2 = save_factor_rankings(df)
        assert n1 == 1
        assert n2 == 1

    def test_run_empty_skipped(self) -> None:
        r = run_factor_ranking(limit=0)
        assert "skipped" in r["status"]
