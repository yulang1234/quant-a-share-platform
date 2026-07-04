import pandas as pd
from src.backtest.position_builder import build_equal_weight_positions, get_rebalance_dates


class TestRebalanceDates:
    def test_daily(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-06"])})
        r = get_rebalance_dates(df, "daily")
        assert len(r) == 3

    def test_weekly(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-05", "2026-01-12", "2026-01-13"])})
        r = get_rebalance_dates(df, "weekly")
        assert len(r) == 2

    def test_monthly(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-05", "2026-01-15", "2026-02-01"])})
        r = get_rebalance_dates(df, "monthly")
        assert len(r) == 2


class TestBuildPositions:
    def test_equal_weight(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02"] * 3, "stock_code": ["000001", "000002", "000003"], "rank_in_strategy": [1, 2, 3]})
        r = build_equal_weight_positions(df, [pd.Timestamp("2026-01-02")], top_k=3)
        assert abs(r["weight"].sum() - 1.0) < 0.001
