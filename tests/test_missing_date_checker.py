"""
Tests for missing_date_checker.py — verifies gap detection in daily series.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_quality.missing_date_checker import check_missing_trade_dates
from src.storage.duckdb_repo import upsert_daily_data


def _to_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert string trade_date values to ``datetime.date`` for DuckDB."""
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _make_row(trade_date: str) -> dict:
    return {
        "stock_code": "000001",
        "trade_date": trade_date,
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": 10.5,
        "pre_close": 10.0,
        "volume": 1000,
        "amount": 10500.0,
        "amplitude": 0.05,
        "pct_change": 0.01,
        "change_amount": 0.5,
        "turnover_rate": 0.02,
    }


class TestMissingDateChecker:
    def test_continuous_dates_no_missing(self, fresh_db) -> None:
        df = pd.DataFrame([_make_row("2024-01-01"), _make_row("2024-01-02")])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_missing_one_day(self, fresh_db) -> None:
        df = pd.DataFrame([_make_row("2024-01-01"), _make_row("2024-01-03")])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        row = result.iloc[0]
        assert row["stock_code"] == "000001"
        assert row["start_date"] == "2024-01-02"
        assert row["end_date"] == "2024-01-02"
        assert row["missing_days"] == 1
        assert row["issue_type"] == "missing_trade_date"
        assert row["issue_level"] == "medium"

    def test_missing_multiple_days(self, fresh_db) -> None:
        df = pd.DataFrame([_make_row("2024-01-01"), _make_row("2024-01-05")])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        row = result.iloc[0]
        assert row["start_date"] == "2024-01-02"
        assert row["end_date"] == "2024-01-04"
        assert row["missing_days"] == 3

    def test_less_than_two_records(self, fresh_db) -> None:
        df = pd.DataFrame([_make_row("2024-01-01")])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_empty_table(self, fresh_db) -> None:
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_specified_stock_code(self, fresh_db) -> None:
        df_a = pd.DataFrame([_make_row("2024-01-01"), _make_row("2024-01-03")])
        df_b = df_a.copy()
        df_b["stock_code"] = "000002"
        upsert_daily_data("stock_daily_raw", _to_trade_dates(pd.concat([df_a, df_b], ignore_index=True)))
        result = check_missing_trade_dates(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_invalid_adj_type(self, fresh_db) -> None:
        with pytest.raises(ValueError, match="Invalid adj_type"):
            check_missing_trade_dates(stock_code="000001", adj_type="bad")
