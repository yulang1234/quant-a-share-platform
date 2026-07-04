"""Tests for src/factor_analysis/forward_returns.py"""
import numpy as np
import pandas as pd
from src.factor_analysis.forward_returns import calculate_forward_returns


class TestForwardReturns:
    def test_basic(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"] * 10, "trade_date": pd.date_range("2026-01-01", periods=10, freq="B"), "close": range(100, 110)})
        r = calculate_forward_returns(df, 5)
        assert "forward_return" in r.columns
        assert r["forward_days"].iloc[0] == 5
        # last 5 rows should be NaN
        assert np.isnan(r["forward_return"].iloc[-1])

    def test_no_cross_stock(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"] * 5 + ["000002"] * 5, "trade_date": pd.date_range("2026-01-01", periods=5, freq="B").tolist() * 2, "close": list(range(100, 105)) + list(range(200, 205))})
        r = calculate_forward_returns(df, 3)
        # first stock: within its 5 rows, last 3 have NaN future_close
        r1 = r[r["stock_code"] == "000001"]
        assert r1["future_close"].iloc[0] == 103  # close[3]
        assert np.isnan(r1["future_close"].iloc[-1])  # last row, future beyond group

    def test_stock_code_6_digit(self) -> None:
        df = pd.DataFrame({"stock_code": [1], "trade_date": ["2026-01-02"], "close": [100]})
        r = calculate_forward_returns(df, 1)
        assert r["stock_code"].iloc[0] == "000001"

    def test_empty(self) -> None:
        r = calculate_forward_returns(pd.DataFrame(), 5)
        assert r.empty
