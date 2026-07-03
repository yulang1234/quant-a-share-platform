"""
Tests for price_checker.py — verifies OHLCV anomaly detection.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_quality.price_checker import check_price_anomalies
from src.storage.duckdb_repo import upsert_daily_data


def _to_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert string trade_date values to ``datetime.date`` for DuckDB."""
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _base_row(close: float = 10.5) -> dict:
    return {
        "stock_code": "000001",
        "trade_date": "2024-01-01",
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": close,
        "pre_close": 10.0,
        "volume": 1000,
        "amount": 10500.0,
        "amplitude": 0.05,
        "pct_change": 0.01,
        "change_amount": 0.5,
        "turnover_rate": 0.02,
    }


class TestPriceChecker:
    def test_normal_data(self, fresh_db) -> None:
        df = pd.DataFrame([_base_row()])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_close_zero(self, fresh_db) -> None:
        row = _base_row()
        row["close"] = 0.0
        df = pd.DataFrame([row])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        assert "close <= 0" in result.iloc[0]["issue_detail"]
        assert result.iloc[0]["issue_level"] == "high"

    def test_high_lower_than_low(self, fresh_db) -> None:
        row = _base_row()
        row["high"] = 8.0
        df = pd.DataFrame([row])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        detail = result.iloc[0]["issue_detail"]
        assert "high < low" in detail
        assert "high < open" in detail
        assert "high < close" in detail

    def test_low_greater_than_close(self, fresh_db) -> None:
        row = _base_row()
        row["low"] = 11.5
        df = pd.DataFrame([row])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        detail = result.iloc[0]["issue_detail"]
        assert "low > close" in detail

    def test_volume_negative(self, fresh_db) -> None:
        row = _base_row()
        row["volume"] = -1
        df = pd.DataFrame([row])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        assert "volume < 0" in result.iloc[0]["issue_detail"]

    def test_amount_negative(self, fresh_db) -> None:
        row = _base_row()
        row["amount"] = -1.0
        df = pd.DataFrame([row])
        upsert_daily_data("stock_daily_raw", _to_trade_dates(df))
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        assert "amount < 0" in result.iloc[0]["issue_detail"]

    def test_empty_table(self, fresh_db) -> None:
        result = check_price_anomalies(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_invalid_adj_type(self, fresh_db) -> None:
        with pytest.raises(ValueError, match="Invalid adj_type"):
            check_price_anomalies(stock_code="000001", adj_type="bad")
