"""Tests for src/data_repair/date_range_repair.py"""

from __future__ import annotations

import pytest

from src.data_repair.date_range_repair import refetch_stock_range


class TestRefetchStockRange:
    def test_dry_run_no_akshare_call(self, fresh_db) -> None:  # noqa: F811
        result = refetch_stock_range(
            "000001", "raw", "20260701", "20260703",
            dry_run=True, confirm=False,
        )
        assert result["status"] == "dry_run"
        assert result["stock_code"] == "000001"

    def test_confirm_false_no_akshare_call(self, fresh_db) -> None:  # noqa: F811
        result = refetch_stock_range(
            "000001", "raw", "20260701", "20260703",
            dry_run=False, confirm=False,
        )
        assert result["status"] == "dry_run"

    def test_invalid_adj_raises(self) -> None:
        with pytest.raises(ValueError, match="adj must be"):
            refetch_stock_range("000001", "invalid", "20260701", "20260703")

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(ValueError, match="must be <="):
            refetch_stock_range("000001", "raw", "20260705", "20260701")

    def test_stock_code_is_6_digit(self) -> None:
        result = refetch_stock_range(1, "raw", "20260701", "20260703")
        assert result["stock_code"] == "000001"
