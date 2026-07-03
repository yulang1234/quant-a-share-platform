"""
Tests for the update log module — uses a temporary DuckDB database to verify
write, query, and de-duplication logic.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data_update.update_log import (
    get_failed_tasks,
    get_recent_update_logs,
    get_update_summary,
    write_update_log,
)
from src.storage.duckdb_repo import close_connection, get_connection, init_database
from src.storage.schema import CREATE_TABLE_SQL


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _tmp_db() -> None:
    """Use a temporary database file for each test to avoid cross-test pollution."""
    close_connection()  # close any existing connection
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test.duckdb"

    con = get_connection(db_path)
    for ddl in CREATE_TABLE_SQL:
        con.execute(ddl)

    yield

    close_connection()
    shutil.rmtree(tmp_dir, ignore_errors=True)


# =====================================================================
#  Write tests
# =====================================================================

class TestWriteUpdateLog:
    def test_write_success(self):
        log_id = write_update_log(
            stock_code="000001",
            task_type="historical_load",
            adj_type="raw",
            start_date="20060101",
            end_date="20260703",
            row_count=4500,
            status="success",
        )
        assert log_id > 0

        # Verify in DB
        con = get_connection()
        row = con.execute(
            "SELECT stock_code, task_type, adj_type, status, row_count "
            "FROM data_update_log WHERE id = ?", [log_id]
        ).fetchone()
        assert row is not None
        assert row[0] == "000001"
        assert row[1] == "historical_load"
        assert row[2] == "raw"
        assert row[3] == "success"
        assert row[4] == 4500

    def test_write_failed(self):
        log_id = write_update_log(
            stock_code="600519",
            task_type="historical_load",
            adj_type="qfq",
            start_date="20200101",
            end_date="20231231",
            row_count=0,
            status="failed",
            error_message="ConnectionError: API timeout",
        )
        assert log_id > 0

        con = get_connection()
        row = con.execute(
            "SELECT stock_code, status, error_message "
            "FROM data_update_log WHERE id = ?", [log_id]
        ).fetchone()
        assert row[0] == "600519"
        assert row[1] == "failed"
        assert "ConnectionError" in row[2]

    def test_write_empty(self):
        log_id = write_update_log(
            stock_code="300001",
            task_type="historical_load",
            adj_type="raw",
            start_date="20200101",
            end_date="20231231",
            row_count=0,
            status="empty",
        )
        assert log_id > 0

    def test_stock_code_has_leading_zeros(self):
        """Verify stock_code with leading zeros is not stripped."""
        log_id = write_update_log(
            stock_code="000001",
            task_type="historical_load",
            adj_type="raw",
            start_date="20200101",
            end_date="20231231",
            row_count=100,
            status="success",
        )
        con = get_connection()
        result = con.execute(
            "SELECT stock_code FROM data_update_log WHERE id = ?", [log_id]
        ).fetchone()
        assert result[0] == "000001"

    def test_auto_id_increment(self):
        """Verify that each write gets a new, incrementing ID."""
        id1 = write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 100, "success")
        id2 = write_update_log("000002", "historical_load", "raw", "20200101", "20231231", 200, "success")
        assert id1 != id2
        assert id2 > id1


# =====================================================================
#  Query tests
# =====================================================================

class TestGetRecentUpdateLogs:
    def test_recent_logs_returns_entries(self):
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 100, "success")
        write_update_log("000002", "historical_load", "qfq", "20200101", "20231231", 200, "success")

        df = get_recent_update_logs(limit=10)
        assert len(df) == 2

    def test_recent_logs_limit(self):
        for i in range(5):
            code = f"{i:06d}"
            write_update_log(code, "historical_load", "raw", "20200101", "20231231", 10, "success")

        df = get_recent_update_logs(limit=3)
        assert len(df) == 3

    def test_empty_logs(self):
        df = get_recent_update_logs()
        assert df.empty


class TestGetUpdateSummary:
    def test_summary_counts(self):
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 100, "success")
        write_update_log("000002", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err")
        write_update_log("000003", "historical_load", "raw", "20200101", "20231231", 0, "empty")
        write_update_log("000004", "historical_load", "qfq", "20200101", "20231231", 0, "skipped")

        summary = get_update_summary()
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["empty"] == 1
        assert summary["skipped"] == 1
        assert summary["total"] == 4


# =====================================================================
#  Get failed tasks — de-duplication logic
# =====================================================================

class TestGetFailedTasks:
    def test_get_failed_returns_failed_only(self):
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err")
        failed = get_failed_tasks()
        assert len(failed) == 1
        assert failed.iloc[0]["stock_code"] == "000001"

    def test_skip_if_later_success(self):
        """If stock_code+adj_type first failed then succeeded, do NOT return as failed."""
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err1")
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 100, "success")

        failed = get_failed_tasks()
        assert len(failed) == 0

    def test_return_if_still_failed(self):
        """If stock_code+adj_type failed and never succeeded, return it."""
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err1")
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err2")

        failed = get_failed_tasks()
        assert len(failed) == 1  # only the latest one
        assert "err2" in failed.iloc[0]["error_message"]

    def test_different_adj_separate(self):
        """Failed raw doesn't affect failed qfq, and vice versa."""
        write_update_log("000001", "historical_load", "raw", "20200101", "20231231", 0, "failed", "err_raw")
        write_update_log("000001", "historical_load", "qfq", "20200101", "20231231", 100, "success")

        failed = get_failed_tasks()
        # raw should still be returned
        codes = failed["stock_code"].tolist()
        adj_types = failed["adj_type"].tolist()
        assert "000001" in codes
        assert "raw" in adj_types
        assert "qfq" not in adj_types

    def test_limit(self):
        for i in range(5):
            code = f"{i:06d}"
            write_update_log(code, "historical_load", "raw", "20200101", "20231231", 0, "failed", "err")

        failed = get_failed_tasks(limit=3)
        assert len(failed) == 3

    def test_empty_when_no_failures(self):
        failed = get_failed_tasks()
        assert failed.empty
