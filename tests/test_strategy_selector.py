"""Tests for src/strategy/selector.py"""
import pandas as pd
from src.strategy.selector import filter_factors_by_effectiveness, run_and_save_strategy


class TestFilterFactors:
    def test_no_summary_returns_all(self) -> None:
        result = filter_factors_by_effectiveness(["a", "b"])
        assert result == ["a", "b"]


class TestAdhocConfig:
    def test_adhoc_does_not_save_config(self, fresh_db) -> None:  # noqa: F811
        """Adhoc strategy does NOT write to strategy_config."""
        from src.storage.duckdb_repo import fetch_strategy_config
        before = len(fetch_strategy_config(active_only=False))
        run_and_save_strategy(
            {"strategy_name": "adhoc_test", "strategy_type": "single_factor",
             "factor_name": "ret20", "top_k": 5},
            save_config=False,
        )
        after = len(fetch_strategy_config(active_only=False))
        assert after == before

    def test_default_saves_config(self, fresh_db) -> None:  # noqa: F811
        """Default strategy DOES write to strategy_config."""
        from src.storage.duckdb_repo import fetch_strategy_config
        before = len(fetch_strategy_config(active_only=False))
        run_and_save_strategy(
            {"strategy_name": "test_save", "strategy_type": "single_factor",
             "factor_name": "ret20", "top_k": 5},
            save_config=True,
        )
        after = len(fetch_strategy_config(active_only=False))
        assert after == before + 1
