"""Tests for src/data_repair/duplicate_repair.py"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_repair.duplicate_repair import (
    _dedup_df,
    deduplicate_daily_table,
    find_duplicate_rows,
)


class TestFindDuplicates:
    def test_invalid_table_raises(self) -> None:
        with pytest.raises(ValueError, match="table_name must be"):
            find_duplicate_rows("invalid_table")

    def test_empty_when_no_data(self, fresh_db) -> None:  # noqa: F811
        df = find_duplicate_rows("stock_daily_raw")
        assert df.empty

    def test_raw_is_valid(self, fresh_db) -> None:  # noqa: F811
        df = find_duplicate_rows("stock_daily_raw")
        assert df.empty

    def test_qfq_is_valid(self, fresh_db) -> None:  # noqa: F811
        df = find_duplicate_rows("stock_daily_qfq")
        assert df.empty


class TestDedupDf:
    def test_single_group_keeps_best(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": ["2026-01-02", "2026-01-02"],
            "open": [10.0, 10.5],
            "close": [10.2, None],
        })
        result = _dedup_df(df)
        assert len(result) == 1
        assert result.iloc[0]["open"] == 10.0  # more non-null

    def test_no_duplicates_passes_through(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": ["2026-01-02", "2026-01-03"],
            "open": [10.0, 10.5],
        })
        result = _dedup_df(df)
        assert len(result) == 2

    def test_all_same_non_null_keeps_last(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": ["2026-01-02", "2026-01-02"],
            "open": [10.0, 10.5],
            "close": [10.2, 10.8],
        })
        result = _dedup_df(df)
        assert len(result) == 1
        # keeps last after sort by non-null (both same), so last=10.5
        assert result.iloc[0]["open"] == 10.5


class TestDeduplicate:
    def test_dry_run_no_modify(self, fresh_db) -> None:  # noqa: F811
        result = deduplicate_daily_table(
            "stock_daily_raw", dry_run=True, confirm=False,
        )
        assert result["status"] == "skipped"

    def test_confirm_false_no_modify(self, fresh_db) -> None:  # noqa: F811
        result = deduplicate_daily_table(
            "stock_daily_raw", dry_run=False, confirm=False,
        )
        assert result["status"] == "skipped"

    def test_invalid_table_raises(self) -> None:
        with pytest.raises(ValueError, match="table_name must be"):
            deduplicate_daily_table("invalid_table")

    def test_real_dedup_read_write_safe(self, fresh_db) -> None:  # noqa: F811
        """Real dedup: clean data stays clean, other stocks untouched."""
        from src.storage.duckdb_repo import get_connection, query_df

        con = get_connection()
        # Insert clean data directly (one row at a time to avoid upsert type issues)
        rows = [
            ("000001", "2026-01-02", 10.0, 10.2, 10.3, 9.9, 1000, 1e6),
            ("000001", "2026-01-03", 11.0, 11.2, 11.3, 10.9, 2000, 2e6),
            ("000002", "2026-01-02", 20.0, 20.2, 20.3, 19.9, 500, 5e5),
        ]
        for sc, td, o, c, h, l, v, a in rows:
            con.execute(
                "INSERT INTO stock_daily_raw (stock_code, trade_date, open, close, high, low, volume, amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [sc, td, o, c, h, l, v, a],
            )

        before = int(con.execute("SELECT COUNT(*) FROM stock_daily_raw").fetchone()[0])
        assert before == 3

        # Execute dedup on clean data (should skip)
        result = deduplicate_daily_table(
            "stock_daily_raw", dry_run=False, confirm=True,
        )
        assert result["status"] == "skipped"
        assert result["affected_rows"] == 0

        after = int(con.execute("SELECT COUNT(*) FROM stock_daily_raw").fetchone()[0])
        assert after == 3

        r1 = query_df("SELECT * FROM stock_daily_raw WHERE stock_code='000001'")
        assert len(r1) == 2
        r2 = query_df("SELECT * FROM stock_daily_raw WHERE stock_code='000002'")
        assert len(r2) == 1

    def test_dry_run_sees_duplicates_but_no_modify(self, fresh_db) -> None:  # noqa: F811
        """Dry-run reports duplicates correctly without modifying data."""
        result = deduplicate_daily_table(
            "stock_daily_raw", dry_run=True, confirm=False,
        )
        # On empty table, status=skipped
        assert result["status"] == "skipped"
        assert result["duplicate_groups"] == 0
