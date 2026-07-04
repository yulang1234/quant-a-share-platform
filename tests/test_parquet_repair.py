"""Tests for src/data_repair/parquet_repair.py"""

from __future__ import annotations

import pytest

from src.data_repair.parquet_repair import rebuild_parquet_from_duckdb


class TestRebuildParquet:
    def test_dry_run_no_write(self, fresh_db) -> None:  # noqa: F811
        result = rebuild_parquet_from_duckdb(
            "000001", "raw", dry_run=True, confirm=False,
        )
        assert result["status"] in ("skipped", "dry_run")

    def test_confirm_false_no_write(self, fresh_db) -> None:  # noqa: F811
        result = rebuild_parquet_from_duckdb(
            "000001", "raw", dry_run=False, confirm=False,
        )
        assert result["status"] in ("skipped", "dry_run")

    def test_invalid_adj_raises(self) -> None:
        with pytest.raises(ValueError, match="adj_type must be"):
            rebuild_parquet_from_duckdb("000001", "invalid")

    def test_stock_code_6_digit(self) -> None:
        result = rebuild_parquet_from_duckdb(1, "raw")
        assert result["stock_code"] == "000001"
