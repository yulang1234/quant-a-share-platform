"""Tests for src/factors/factor_calculator.py"""
import pandas as pd
from src.factors.factor_calculator import calculate_daily_factors, run_factor_calculation, save_daily_factors


class TestCalculateDailyFactors:
    def test_empty_returns_empty(self) -> None:
        result = calculate_daily_factors(pd.DataFrame())
        assert result.empty

    def test_all_expected_columns(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001"] * 70,
            "trade_date": pd.date_range("2026-01-01", periods=70, freq="B"),
            "close": range(100, 170), "open": range(99, 169),
            "high": range(101, 171), "low": range(98, 168),
            "volume": [1000] * 70, "amount": [1e6] * 70,
            "turnover_rate": [0.5] * 70,
        })
        result = calculate_daily_factors(df)
        assert "return_1d" in result.columns
        assert "ma20" in result.columns
        assert "volatility_20d" in result.columns
        assert "volume_ma5" in result.columns
        assert "price_position_20d" in result.columns
        assert "factor_date" in result.columns
        assert "source_adj" in result.columns

    def test_no_modify_input(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001"] * 10,
            "trade_date": pd.date_range("2026-01-01", periods=10, freq="B"),
            "close": range(100, 110), "open": range(99, 109),
            "high": range(101, 111), "low": range(98, 108),
            "volume": [1000] * 10, "amount": [1e6] * 10,
        })
        orig_cols = set(df.columns)
        calculate_daily_factors(df)
        assert set(df.columns) == orig_cols


class TestSaveFactors:
    def test_empty_returns_zero(self, fresh_db) -> None:  # noqa: F811
        assert save_daily_factors(pd.DataFrame()) == 0
        assert save_daily_factors(None) == 0

    def test_upsert_idempotent(self, fresh_db) -> None:  # noqa: F811
        df = pd.DataFrame({
            "stock_code": ["000001"], "trade_date": [pd.Timestamp("2026-01-02").date()],
            "return_1d": [0.01], "source_adj": ["qfq"],
        })
        n1 = save_daily_factors(df)
        n2 = save_daily_factors(df)
        assert n1 == 1
        assert n2 == 1  # upsert, not duplicate

    def test_save_does_not_modify_other_stocks(self, fresh_db) -> None:  # noqa: F811
        from src.storage.duckdb_repo import fetch_daily_factors
        save_daily_factors(pd.DataFrame({
            "stock_code": ["000001"], "trade_date": [pd.Timestamp("2026-01-02").date()],
            "return_1d": [0.01], "source_adj": ["qfq"],
        }))
        save_daily_factors(pd.DataFrame({
            "stock_code": ["000002"], "trade_date": [pd.Timestamp("2026-01-02").date()],
            "return_1d": [0.02], "source_adj": ["qfq"],
        }))
        r = fetch_daily_factors()
        assert len(r) == 2


class TestRunFactorCalculation:
    def test_empty_qfq_skipped(self) -> None:
        result = run_factor_calculation(stock_code="999999")
        assert result["source_rows"] == 0
        assert "skipped" in result["status"]

    def test_limit_respected(self) -> None:
        result = run_factor_calculation(limit=0)
        assert result["source_rows"] == 0
