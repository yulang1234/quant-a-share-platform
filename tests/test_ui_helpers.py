"""Tests for ui/components/ui_helpers.py"""
from ui.components.ui_helpers import safe_fetch_table_count, safe_fetch_latest_date, safe_fetch_sample


class TestUIHelpers:
    def test_count_table_missing(self) -> None:
        assert safe_fetch_table_count("nonexistent_table_xyz") == 0

    def test_latest_date_missing(self) -> None:
        assert safe_fetch_latest_date("nonexistent_table_xyz") is None

    def test_sample_missing(self) -> None:
        df = safe_fetch_sample("nonexistent_table_xyz", 5)
        assert df.empty

    def test_count_real_table(self) -> None:
        cnt = safe_fetch_table_count("stock_pool")
        assert cnt >= 0
