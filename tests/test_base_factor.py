"""Tests for src/factors/base_factor.py"""
import numpy as np
import pandas as pd
import pytest
from src.factors.base_factor import ensure_factor_columns, safe_divide, validate_factor_input


class TestValidateFactorInput:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_factor_input(pd.DataFrame())

    def test_missing_close_raises(self) -> None:
        with pytest.raises(ValueError, match="close"):
            validate_factor_input(pd.DataFrame({"x": [1]}))

    def test_stock_code_6_digit(self) -> None:
        df = pd.DataFrame({"stock_code": [1, 600519], "trade_date": ["2026-01-02", "2026-01-03"], "close": [10, 20]})
        result = validate_factor_input(df)
        assert result["stock_code"].iloc[0] == "000001"

    def test_does_not_modify_input(self) -> None:
        original = pd.DataFrame({"stock_code": ["000001"], "trade_date": ["2026-01-02"], "close": [10.0]})
        copy_df = original.copy()
        validate_factor_input(original)
        assert original.equals(copy_df)


class TestSafeDivide:
    def test_normal(self) -> None:
        r = safe_divide(pd.Series([10.0]), pd.Series([2.0]))
        assert r.iloc[0] == 5.0

    def test_divide_by_zero(self) -> None:
        r = safe_divide(pd.Series([10.0]), pd.Series([0.0]))
        assert np.isnan(r.iloc[0])

    def test_divide_by_nan(self) -> None:
        r = safe_divide(pd.Series([10.0]), pd.Series([np.nan]))
        assert np.isnan(r.iloc[0])


class TestEnsureFactorColumns:
    def test_adds_missing(self) -> None:
        df = pd.DataFrame({"a": [1]})
        result = ensure_factor_columns(df, ["a", "b"])
        assert "b" in result.columns
        assert np.isnan(result["b"].iloc[0])
