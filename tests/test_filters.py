"""
Tests for the stock filters module (src/universe/filters.py).
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.universe.filters import (
    apply_basic_filters,
    filter_low_liquidity,
    filter_new_stocks,
    filter_st_stocks,
    filter_suspended_stocks,
)


# ── Shared fixture ──────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "stock_code": ["000001", "600519", "300750", "000858"],
        "stock_name": ["平安银行", "贵州茅台", "宁德时代", "*ST五粮"],
        "is_active": [True, True, True, True],
    })


# ======================================================================
#  filter_st_stocks
# ======================================================================

class TestFilterST:
    def test_removes_st_stocks(self, sample_df: pd.DataFrame) -> None:
        result = filter_st_stocks(sample_df)
        assert len(result) == 3
        assert "*ST五粮" not in result["stock_name"].values

    def test_returns_all_if_no_st(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "stock_name": ["平安银行", "贵州茅台"],
        })
        result = filter_st_stocks(df)
        assert len(result) == 2

    def test_handles_missing_column(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"]})
        result = filter_st_stocks(df)  # should not raise
        assert len(result) == 1

    def test_does_not_modify_original(self, sample_df: pd.DataFrame) -> None:
        original_len = len(sample_df)
        filter_st_stocks(sample_df)
        assert len(sample_df) == original_len


# ======================================================================
#  filter_new_stocks
# ======================================================================

class TestFilterNew:
    def test_removes_new_stocks(self) -> None:
        today = datetime.now()
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "stock_name": ["平安银行", "贵州茅台"],
            "list_date": [
                today - timedelta(days=365 * 10),  # 10 years ago
                today - timedelta(days=30),          # 30 days ago — too new
            ],
        })
        result = filter_new_stocks(df, min_days=180)
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_handles_missing_column(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"]})
        result = filter_new_stocks(df)
        assert len(result) == 1

    def test_returns_all_if_no_list_date(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "stock_name": ["平安银行", "贵州茅台"],
        })
        result = filter_new_stocks(df)
        assert len(result) == 2


# ======================================================================
#  filter_low_liquidity
# ======================================================================

class TestFilterLiquidity:
    def test_removes_low_liquidity(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "amount_mean_20": [500_000_000, 50_000_000],  # 5亿 vs 5千万
        })
        result = filter_low_liquidity(df, min_amount=100_000_000)
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_handles_missing_column(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"]})
        result = filter_low_liquidity(df)
        assert len(result) == 1


# ======================================================================
#  filter_suspended_stocks
# ======================================================================

class TestFilterSuspended:
    def test_removes_suspended_stocks(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "status": ["正常", "停牌"],
        })
        result = filter_suspended_stocks(df)
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_handles_missing_column(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"]})
        result = filter_suspended_stocks(df)
        assert len(result) == 1


# ======================================================================
#  apply_basic_filters
# ======================================================================

class TestApplyBasicFilters:
    def test_returns_all_when_fields_missing(self) -> None:
        """Without list_date, amount_mean_20, status — should not crash."""
        df = pd.DataFrame({
            "stock_code": ["000001", "600519", "300750"],
            "stock_name": ["平安银行", "贵州茅台", "宁德时代"],
            "is_active": [True, True, True],
        })
        result = apply_basic_filters(df)
        # Should return all since no ST names and missing columns are skipped
        assert len(result) == 3

    def test_combines_all_filters(self) -> None:
        today = datetime.now()
        df = pd.DataFrame({
            "stock_code": ["000001", "600519", "300750"],
            "stock_name": ["平安银行", "*ST茅台", "宁德时代"],
            "list_date": [
                today - timedelta(days=365 * 10),
                today - timedelta(days=365 * 10),
                today - timedelta(days=30),
            ],
            "amount_mean_20": [500_000_000, 100_000_000, 10_000_000],
            "status": ["正常", "正常", "停牌"],
        })
        result = apply_basic_filters(df)
        # 000001 should survive, 600519 (ST) removed, 300750 (new+suspended) removed
        assert len(result) == 1
        assert result.iloc[0]["stock_code"] == "000001"

    def test_handles_empty_dataframe(self) -> None:
        df = pd.DataFrame({
            "stock_code": pd.Series(dtype=str),
            "stock_name": pd.Series(dtype=str),
        })
        result = apply_basic_filters(df)
        assert len(result) == 0

    def test_does_not_modify_original(self) -> None:
        df = pd.DataFrame({
            "stock_code": ["000001", "600519"],
            "stock_name": ["平安银行", "*ST茅台"],
        })
        original_len = len(df)
        apply_basic_filters(df)
        assert len(df) == original_len
