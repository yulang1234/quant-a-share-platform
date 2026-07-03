"""
Tests for the Parquet repository — verifies save, read, merge, and
de-duplication behaviour for per-stock daily data files.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.storage.parquet_repo import read_daily_parquet, save_daily_parquet, _validate_adj_type, _get_file_path

# We need to override the parquet root for tests
from config.settings import get_parquet_root


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _tmp_parquet_root(monkeypatch) -> None:
    """Redirect parquet root to a temporary directory."""
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir)

    def mock_get_root() -> Path:
        return tmp_path

    # Patch at the point of use (parquet_repo module)
    monkeypatch.setattr("src.storage.parquet_repo.get_parquet_root", mock_get_root)

    yield

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def sample_df_raw() -> pd.DataFrame:
    return pd.DataFrame({
        "stock_code": ["000001", "000001", "000001"],
        "trade_date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]).date,
        "open": [10.0, 10.5, 10.3],
        "close": [10.2, 10.8, 10.1],
        "high": [10.3, 11.0, 10.5],
        "low": [9.9, 10.4, 10.0],
        "volume": [1000000, 1500000, 1200000],
        "amount": [1e7, 1.6e7, 1.2e7],
        "pct_change": [0.02, 0.0588, -0.0648],
    })


# =====================================================================
#  Save & read tests
# =====================================================================

class TestSaveDailyParquet:
    def test_save_new_file(self, sample_df_raw):
        """Save a new parquet file that doesn't exist yet."""
        n = save_daily_parquet(sample_df_raw, "000001", "raw")
        assert n == 3  # 3 rows

        # Verify file exists
        p = get_parquet_root() / "dwd/daily_raw/000001.parquet"
        assert p.exists()

    def test_save_qfq(self, sample_df_raw):
        """Save to the qfq directory."""
        n = save_daily_parquet(sample_df_raw, "000001", "qfq")
        assert n == 3

        p = get_parquet_root() / "dwd/daily_qfq/000001.parquet"
        assert p.exists()

    def test_merge_with_existing(self, sample_df_raw):
        """Save, then save new data, then verify merge."""
        # First save: 3 rows
        save_daily_parquet(sample_df_raw, "000001", "raw")

        # New data with 2 more rows
        new_data = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": pd.to_datetime(["2024-01-05", "2024-01-06"]).date,
            "open": [10.0, 10.5],
            "close": [10.2, 10.8],
            "high": [10.3, 11.0],
            "low": [9.9, 10.4],
            "volume": [1000000, 1500000],
            "amount": [1e7, 1.6e7],
            "pct_change": [0.02, 0.0588],
        })
        n = save_daily_parquet(new_data, "000001", "raw")
        assert n == 5  # 3 + 2

    def test_deduplicate_on_save(self, sample_df_raw):
        """Save, then save overlapping data, verify dedup."""
        save_daily_parquet(sample_df_raw, "000001", "raw")

        # Overlapping data (same dates, different close values)
        overlap = pd.DataFrame({
            "stock_code": ["000001", "000001"],
            "trade_date": pd.to_datetime(["2024-01-03", "2024-01-04"]).date,
            "open": [10.5, 10.3],
            "close": [99.9, 99.9],  # changed values
            "high": [11.0, 10.5],
            "low": [10.4, 10.0],
            "volume": [1500000, 1200000],
            "amount": [1.6e7, 1.2e7],
            "pct_change": [0.0588, -0.0648],
        })
        n = save_daily_parquet(overlap, "000001", "raw")
        assert n == 3  # still 3 rows (no new dates)

        # Verify the overlapping row was updated (keep="last")
        df_read = read_daily_parquet("000001", "raw")
        row_03 = df_read[df_read["trade_date"] == pd.to_datetime("2024-01-03").date()]
        assert row_03["close"].iloc[0] == 99.9

    def test_trade_date_sorted(self, sample_df_raw):
        """Verify data is sorted by trade_date."""
        unsorted = sample_df_raw.iloc[::-1].reset_index(drop=True)  # reverse order
        save_daily_parquet(unsorted, "000001", "raw")
        df_read = read_daily_parquet("000001", "raw")
        dates = df_read["trade_date"].tolist()
        assert dates == sorted(dates)

    def test_empty_df(self):
        """Saving an empty DataFrame should create the file (empty)."""
        n = save_daily_parquet(pd.DataFrame(), "000001", "raw")
        assert n == 0

        p = get_parquet_root() / "dwd/daily_raw/000001.parquet"
        assert p.exists()

    def test_stock_code_6_digit_string(self, sample_df_raw):
        """Verify stock_code is normalised to 6 digits."""
        save_daily_parquet(sample_df_raw, 1, "raw")  # int input
        p = get_parquet_root() / "dwd/daily_raw/000001.parquet"
        assert p.exists()

        df_read = read_daily_parquet("1", "raw")  # short string input
        assert not df_read.empty
        assert all(df_read["stock_code"] == "000001")


class TestReadDailyParquet:
    def test_read_nonexistent(self):
        """Reading a non-existent file returns an empty DataFrame."""
        df = read_daily_parquet("999999", "raw")
        assert df.empty

    def test_read_after_save(self, sample_df_raw):
        save_daily_parquet(sample_df_raw, "000001", "raw")
        df = read_daily_parquet("000001", "raw")
        assert len(df) == 3
        assert list(df.columns) == list(sample_df_raw.columns)


# =====================================================================
#  adj_type validation
# =====================================================================

class TestAdjTypeValidation:
    def test_invalid_adj_type_save(self, sample_df_raw):
        """save_daily_parquet with invalid adj_type must raise ValueError."""
        with pytest.raises(ValueError, match="adj_type must be"):
            save_daily_parquet(sample_df_raw, "000001", "invalid")

    def test_invalid_adj_type_read(self):
        """read_daily_parquet with invalid adj_type must raise ValueError."""
        with pytest.raises(ValueError, match="adj_type must be"):
            read_daily_parquet("000001", "invalid")

    def test_invalid_adj_type_get_path(self):
        """_get_file_path with invalid adj_type must raise ValueError."""
        with pytest.raises(ValueError, match="adj_type must be"):
            _get_file_path("000001", "invalid")

    def test_validate_adj_type_valid(self):
        """_validate_adj_type accepts raw and qfq."""
        _validate_adj_type("raw")   # no raise
        _validate_adj_type("qfq")   # no raise

    def test_validate_adj_type_invalid(self):
        """_validate_adj_type raises for anything else."""
        with pytest.raises(ValueError, match="adj_type must be"):
            _validate_adj_type("hfq")
        with pytest.raises(ValueError, match="adj_type must be"):
            _validate_adj_type("")
        with pytest.raises(ValueError, match="adj_type must be"):
            _validate_adj_type("raw ")  # trailing space


# =====================================================================
#  Input side-effect protection
# =====================================================================

class TestInputSideEffects:
    def test_save_does_not_mutate_input(self, sample_df_raw):
        """save_daily_parquet must NOT modify the caller's DataFrame."""
        original_cols = list(sample_df_raw.columns)
        original_stock_code = sample_df_raw["stock_code"].iloc[0]
        original_trade_date = sample_df_raw["trade_date"].iloc[0]

        save_daily_parquet(sample_df_raw, "000001", "raw")

        # Columns must be unchanged
        assert list(sample_df_raw.columns) == original_cols
        # stock_code value must not be overwritten
        assert sample_df_raw["stock_code"].iloc[0] == original_stock_code
        # trade_date must not be mutated
        assert sample_df_raw["trade_date"].iloc[0] == original_trade_date

    def test_save_does_not_mutate_empty_input(self):
        """Saving an empty DataFrame must not raise."""
        empty = pd.DataFrame()
        n = save_daily_parquet(empty, "000001", "raw")
        assert n == 0
        # Original must still be empty
        assert empty.empty
