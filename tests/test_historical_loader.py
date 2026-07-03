"""
Tests for the historical data loader — verifies the orchestration logic,
including success / empty / failed scenarios, limit parameter, and
idempotent re-execution.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data_update.historical_loader import load_historical_data, load_one_stock
from src.data_update.update_log import get_update_summary, get_recent_update_logs
from src.storage.duckdb_repo import close_connection, get_connection, init_database, query_df
from src.storage.schema import CREATE_TABLE_SQL

# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _tmp_db() -> Generator[None, None, None]:
    """Use a temporary database for each test."""
    close_connection()
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test.duckdb"

    con = get_connection(db_path)
    for ddl in CREATE_TABLE_SQL:
        try:
            con.execute(ddl)
        except Exception as e:
            close_connection()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to execute DDL: {e}") from e

    yield

    close_connection()
    shutil.rmtree(tmp_dir, ignore_errors=True)


def _seed_stock_pool(stock_codes: list[str]) -> None:
    """Insert test stocks into the stock_pool table."""
    con = get_connection()
    for i, code in enumerate(stock_codes):
        con.execute(
            "INSERT INTO stock_pool "
            "(stock_code, stock_name, pool_name, is_active, is_blacklisted) "
            "VALUES (?, ?, 'core_500', TRUE, FALSE)",
            [code, f"Test Stock {i}"],
        )


class FakeAkShare:
    """Replacement for the real ``akshare`` module."""

    @staticmethod
    def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
        return pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "开盘": [10.0, 10.5],
            "收盘": [10.2, 10.8],
            "最高": [10.3, 11.0],
            "最低": [9.9, 10.4],
            "成交量": [1000000, 1500000],
            "成交额": [1e7, 1.6e7],
            "振幅": [0.04, 0.06],
            "涨跌幅": [0.02, 0.0588],
            "涨跌额": [0.2, 0.6],
            "换手率": [0.005, 0.008],
        })


@pytest.fixture(autouse=True)
def _mock_akshare_module(monkeypatch) -> None:
    """Replace ``AkShareClient._get_akshare_module`` with FakeAkShare."""
    from src.data_source.akshare_client import AkShareClient
    monkeypatch.setattr(
        AkShareClient,
        "_get_akshare_module",
        staticmethod(lambda: FakeAkShare),
    )


def _mock_akshare(monkeypatch, return_df: pd.DataFrame | None = None, raise_error: Exception | None = None) -> None:
    """Replace ``FakeAkShare.stock_zh_a_hist`` with a custom mock."""

    def mock_hist(symbol, period, start_date, end_date, adjust):
        if raise_error:
            raise raise_error
        if return_df is not None:
            return return_df
        return pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "开盘": [10.0, 10.5],
            "收盘": [10.2, 10.8],
            "最高": [10.3, 11.0],
            "最低": [9.9, 10.4],
            "成交量": [1000000, 1500000],
            "成交额": [1e7, 1.6e7],
            "振幅": [0.04, 0.06],
            "涨跌幅": [0.02, 0.0588],
            "涨跌额": [0.2, 0.6],
            "换手率": [0.005, 0.008],
        })

    monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))


# =====================================================================
#  load_one_stock tests
# =====================================================================

class TestLoadOneStock:
    def test_success(self, monkeypatch):
        """Test a successful single-stock load."""
        _mock_akshare(monkeypatch)
        result = load_one_stock("000001", "20240101", "20240131", "raw", sleep_seconds=0)
        assert result["status"] == "success"
        assert result["row_count"] == 2
        assert result["adj_type"] == "raw"
        assert result["stock_code"] == "000001"

    def test_empty(self, monkeypatch):
        """Test when akshare returns empty DataFrame."""
        _mock_akshare(monkeypatch, return_df=pd.DataFrame())
        result = load_one_stock("000001", "20240101", "20240131", "raw", sleep_seconds=0)
        assert result["status"] == "empty"
        assert result["row_count"] == 0

    def test_failed(self, monkeypatch):
        """Test when akshare raises an exception."""
        _mock_akshare(monkeypatch, raise_error=ConnectionError("API timeout"))
        result = load_one_stock("000001", "20240101", "20240131", "raw", sleep_seconds=0)
        assert result["status"] == "failed"
        assert result["error_message"] is not None
        assert "ConnectionError" in result["error_message"]

    def test_qfq_success(self, monkeypatch):
        """Test successful QFQ load."""
        _mock_akshare(monkeypatch)
        result = load_one_stock("000001", "20240101", "20240131", "qfq", sleep_seconds=0)
        assert result["status"] == "success"
        assert result["adj_type"] == "qfq"


# =====================================================================
#  load_historical_data tests
# =====================================================================

class TestLoadHistoricalData:
    def test_limit_parameter(self, monkeypatch):
        """Test that the limit parameter correctly restricts stock count."""
        _seed_stock_pool(["000001", "000002", "000003", "000004", "000005"])
        _mock_akshare(monkeypatch)

        # Only process 2 stocks (raw + qfq = 4 tasks)
        summary = load_historical_data(
            pool_name="core_500",
            start_date="20240101",
            end_date="20240131",
            limit=2,
            adj="all",
            sleep_seconds=0,
        )
        assert summary["total"] == 4  # 2 stocks × 2 adj types
        assert summary["success"] == 4

    def test_limit_raw_only(self, monkeypatch):
        """Test limit with adj='raw' — only raw tasks run."""
        _seed_stock_pool(["000001", "000002"])
        _mock_akshare(monkeypatch)

        summary = load_historical_data(
            pool_name="core_500",
            start_date="20240101",
            end_date="20240131",
            limit=1,
            adj="raw",
            sleep_seconds=0,
        )
        assert summary["total"] == 1  # 1 stock × 1 adj type
        assert summary["success"] == 1

    def test_partial_failure_no_interruption(self, monkeypatch):
        """Test that one stock's failure doesn't stop others."""
        _seed_stock_pool(["000001", "000002", "000003"])

        call_count = [0]

        def mock_hist(symbol, period, start_date, end_date, adjust):
            call_count[0] += 1
            if call_count[0] == 2:  # second call fails
                raise ConnectionError("Mock failure")
            return pd.DataFrame({
                "日期": ["2024-01-02"],
                "开盘": [10.0],
                "收盘": [10.2],
                "最高": [10.3],
                "最低": [9.9],
                "成交量": [1000000],
                "成交额": [1e7],
                "振幅": [0.04],
                "涨跌幅": [0.02],
                "涨跌额": [0.2],
                "换手率": [0.005],
            })

        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))

        summary = load_historical_data(
            pool_name="core_500",
            start_date="20240101",
            end_date="20240131",
            limit=3,
            adj="raw",
            sleep_seconds=0,
        )
        assert summary["total"] == 3
        assert summary["success"] == 2  # first and third succeed
        assert summary["failed"] == 1   # second fails

    def test_idempotent_repeat(self, monkeypatch):
        """Test that repeating the same load does not create duplicates."""
        _seed_stock_pool(["000001"])
        _mock_akshare(monkeypatch)

        # First run
        s1 = load_historical_data("core_500", "20240101", "20240131", limit=1, adj="raw", sleep_seconds=0)
        assert s1["success"] == 1

        rows_after_first = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_raw").iloc[0]["cnt"]

        # Second run (same data)
        s2 = load_historical_data("core_500", "20240101", "20240131", limit=1, adj="raw", sleep_seconds=0)
        assert s2["success"] == 1

        rows_after_second = query_df("SELECT COUNT(*) AS cnt FROM stock_daily_raw").iloc[0]["cnt"]

        # Row count should be the same (upsert, not duplicate)
        assert rows_after_first == rows_after_second

    def test_empty_pool(self, monkeypatch):
        """Test that an empty stock pool returns a zero summary."""
        # Don't seed any stocks
        summary = load_historical_data(
            pool_name="core_500",
            start_date="20240101",
            end_date="20240131",
            limit=5,
            adj="all",
            sleep_seconds=0,
        )
        assert summary["total"] == 0

    def test_logs_written(self, monkeypatch):
        """Test that log entries are written during load."""
        _seed_stock_pool(["000001"])
        _mock_akshare(monkeypatch)

        load_historical_data("core_500", "20240101", "20240131", limit=1, adj="raw", sleep_seconds=0)

        logs = get_recent_update_logs()
        assert len(logs) == 1
        assert logs.iloc[0]["status"] == "success"
        assert logs.iloc[0]["stock_code"] == "000001"

    def test_parquet_file_created(self, monkeypatch, tmp_path):
        """Test that parquet files are created during load."""
        # Redirect parquet root at the point of use
        monkeypatch.setattr("src.storage.parquet_repo.get_parquet_root", lambda: tmp_path)

        _seed_stock_pool(["000001"])
        _mock_akshare(monkeypatch)

        load_historical_data("core_500", "20240101", "20240131", limit=1, adj="raw", sleep_seconds=0)

        parquet_path = tmp_path / "dwd/daily_raw/000001.parquet"
        assert parquet_path.exists()
