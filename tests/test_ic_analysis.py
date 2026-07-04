"""Tests for src/factor_analysis/ic_analysis.py"""
import pandas as pd
from src.factor_analysis.ic_analysis import calculate_daily_ic


class TestIC:
    def test_basic(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000002", "000003"], "trade_date": pd.to_datetime(["2026-01-02"] * 3), "factor_name": ["ret20"] * 3, "direction_value": [0.1, 0.2, 0.3]})
        fwd = pd.DataFrame({"stock_code": ["000001", "000002", "000003"], "trade_date": pd.to_datetime(["2026-01-02"] * 3), "forward_return": [0.01, 0.02, 0.03]})
        r = calculate_daily_ic(rank, fwd, "ret20", 5)
        assert not r.empty
        assert "ic" in r.columns
        assert "rank_ic" in r.columns

    def test_small_sample_returns_nan(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000002"], "trade_date": pd.to_datetime(["2026-01-02"] * 2), "factor_name": ["ret20"] * 2, "direction_value": [0.1, 0.2]})
        fwd = pd.DataFrame({"stock_code": ["000001", "000002"], "trade_date": pd.to_datetime(["2026-01-02"] * 2), "forward_return": [0.01, 0.02]})
        r = calculate_daily_ic(rank, fwd, "ret20", 5)
        assert pd.isna(r["ic"].iloc[0])

    def test_empty_rank(self) -> None:
        r = calculate_daily_ic(pd.DataFrame(), pd.DataFrame({"stock_code": ["000001"], "trade_date": ["2026-01-02"], "forward_return": [0.01]}), "x")
        assert r.empty
