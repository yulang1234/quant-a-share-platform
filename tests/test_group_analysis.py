"""Tests for src/factor_analysis/group_analysis.py"""
import pandas as pd
from src.factor_analysis.group_analysis import assign_factor_groups, calculate_group_returns


class TestGroupAnalysis:
    def test_assign_groups(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"] * 10, "trade_date": pd.to_datetime(["2026-01-02"] * 10), "factor_name": ["ret20"] * 10, "direction_value": range(10)})
        r = assign_factor_groups(df, 5)
        assert "group_id" in r.columns
        assert r["group_id"].max() == 5

    def test_calculate_group_returns(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000002", "000003", "000004", "000005"], "trade_date": pd.to_datetime(["2026-01-02"] * 5), "factor_name": ["ret20"] * 5, "direction_value": [1, 2, 3, 4, 5]})
        fwd = pd.DataFrame({"stock_code": ["000001", "000002", "000003", "000004", "000005"], "trade_date": pd.to_datetime(["2026-01-02"] * 5), "forward_return": [0.01, 0.02, 0.03, 0.04, 0.05]})
        r = calculate_group_returns(rank, fwd, "ret20", 5, 5)
        assert not r.empty
        assert "avg_forward_return" in r.columns
