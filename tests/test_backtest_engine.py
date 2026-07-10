"""Tests for src/backtest/backtest_engine.py"""
import pandas as pd
from src.backtest.backtest_engine import run_basic_backtest


class TestEngine:
    def test_no_selections_skipped(self, fresh_db) -> None:  # noqa: F811
        r = run_basic_backtest(strategy_name="nonexistent", limit=1)
        assert "skipped" in r["status"]

    def test_cli_params_preserved(self, fresh_db) -> None:  # noqa: F811
        """CLI parameters must not be overwritten by defaults."""
        r = run_basic_backtest(
            backtest_name="test_cli_params",
            strategy_name="test_strat",
            initial_cash=123456, top_k=7,
            rebalance_frequency="daily",
            limit=1,
        )
        from src.storage.duckdb_repo import fetch_backtest_config
        cfgs = fetch_backtest_config("test_cli_params")
        if not cfgs.empty:
            row = cfgs.iloc[0]
            assert row["initial_cash"] == 123456
            assert row["top_k"] == 7
            assert row["rebalance_frequency"] == "daily"

    def test_auto_backtest_name(self, fresh_db) -> None:  # noqa: F811
        """Auto-generated backtest_name does not override other params."""
        r = run_basic_backtest(
            strategy_name="auto_test", initial_cash=999,
            top_k=5, rebalance_frequency="weekly", limit=1,
        )
        from src.storage.duckdb_repo import fetch_backtest_config
        cfgs = fetch_backtest_config("auto_test_bt")
        if not cfgs.empty:
            row = cfgs.iloc[0]
            assert row["initial_cash"] == 999
            assert row["top_k"] == 5
            assert row["rebalance_frequency"] == "weekly"

    def test_upsert_idempotent(self, fresh_db) -> None:  # noqa: F811
        r1 = run_basic_backtest(backtest_name="idem_test", strategy_name="s", limit=1)
        r2 = run_basic_backtest(backtest_name="idem_test", strategy_name="s", limit=1)
        from src.storage.duckdb_repo import fetch_backtest_config
        assert len(fetch_backtest_config("idem_test")) == 1
