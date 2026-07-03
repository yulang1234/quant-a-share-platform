"""
Tests for duplicate_checker.py — verifies duplicate (stock_code, trade_date)
detection in stock_daily_raw / stock_daily_qfq.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_quality.duplicate_checker import check_duplicate_daily_data
from src.storage.duckdb_repo import get_connection, upsert_daily_data


def _to_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert string trade_date values to ``datetime.date`` for DuckDB."""
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _prepare_raw_table_without_pk() -> None:
    """Recreate ``stock_daily_raw`` without a primary key so duplicates can exist."""
    con = get_connection()
    con.execute("DROP TABLE IF EXISTS stock_daily_raw")
    con.execute(
        """
        CREATE TABLE stock_daily_raw (
            stock_code      VARCHAR(6)   NOT NULL,
            trade_date      DATE         NOT NULL,
            open            DECIMAL(12,2),
            high            DECIMAL(12,2),
            low             DECIMAL(12,2),
            close           DECIMAL(12,2),
            pre_close       DECIMAL(12,2),
            volume          BIGINT,
            amount          DECIMAL(16,2),
            amplitude       DECIMAL(8,4),
            pct_change      DECIMAL(8,4),
            change_amount   DECIMAL(12,2),
            turnover_rate   DECIMAL(8,4),
            data_source     VARCHAR(16)  DEFAULT 'akshare',
            created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _seed_unique_rows(fresh_db) -> None:
    """Insert two unique rows for stock 000001."""
    df = pd.DataFrame(
        [
            {
                "stock_code": "000001",
                "trade_date": "2024-01-01",
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
            },
            {
                "stock_code": "000001",
                "trade_date": "2024-01-02",
                "open": 10.5,
                "high": 11.5,
                "low": 10.0,
                "close": 11.0,
                "pre_close": 10.5,
                "volume": 1100,
                "amount": 11500.0,
                "amplitude": 0.05,
                "pct_change": 0.01,
                "change_amount": 0.5,
                "turnover_rate": 0.02,
            },
        ]
    )
    upsert_daily_data("stock_daily_raw", _to_trade_dates(df))


def _seed_duplicate_rows(fresh_db) -> None:
    """Insert a duplicate (000001, 2024-01-01) directly via SQL."""
    _seed_unique_rows(fresh_db)
    con = get_connection()
    con.execute(
        """
        INSERT INTO stock_daily_raw
        (stock_code, trade_date, open, high, low, close, volume, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["000001", "2024-01-01", 10.0, 11.0, 9.5, 10.5, 1000, 10500.0],
    )


class TestDuplicateChecker:
    def test_no_duplicates(self, fresh_db) -> None:
        _prepare_raw_table_without_pk()
        _seed_unique_rows(fresh_db)
        result = check_duplicate_daily_data(stock_code="000001", adj_type="raw")
        assert result.empty

    def test_has_duplicates(self, fresh_db) -> None:
        _prepare_raw_table_without_pk()
        _seed_duplicate_rows(fresh_db)
        result = check_duplicate_daily_data(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        row = result.iloc[0]
        assert row["stock_code"] == "000001"
        assert row["trade_date"] == "2024-01-01"
        assert row["duplicate_count"] == 2
        assert row["adj_type"] == "raw"
        assert row["issue_type"] == "duplicate_record"
        assert row["issue_level"] == "high"
        assert "count: 2" in row["issue_detail"]

    def test_specified_stock_code_only(self, fresh_db) -> None:
        _prepare_raw_table_without_pk()
        _seed_duplicate_rows(fresh_db)
        con = get_connection()
        con.execute(
            """
            INSERT INTO stock_daily_raw
            (stock_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ["000002", "2024-01-01", 10.0, 11.0, 9.5, 10.5, 1000, 10500.0],
        )
        con.execute(
            """
            INSERT INTO stock_daily_raw
            (stock_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ["000002", "2024-01-01", 10.0, 11.0, 9.5, 10.5, 1000, 10500.0],
        )
        result = check_duplicate_daily_data(stock_code="000001", adj_type="raw")
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_invalid_adj_type(self, fresh_db) -> None:
        with pytest.raises(ValueError, match="Invalid adj_type"):
            check_duplicate_daily_data(stock_code="000001", adj_type="bad")
